from datetime import timedelta
from pprint import pprint
import asyncio
import logging
import pandas as pd
import random

from trading import strategy
from trading import exchanges
from utils import config, \
                  load_keys, \
                  utc_now, \
                  rounddown_dt, \
                  roundup_dt, \
                  filter_by, \
                  smallest_tf, \
                  alert_sound, \
                  is_within, \
                  timeframe_timedelta

from analysis.hist_data import build_ohlcv

logger = logging.getLogger()


class SingleEXTrader():

    def __init__(self, mongo, ex_id, strategy_name,
                 custom_config=None,
                 ccxt_verbose=False,
                 enable_trade=True,
                 log=False):
        self.mongo = mongo
        self._config = custom_config if custom_config else config
        self.config = self._config['trading']
        self.log = log
        self.enable_trade = enable_trade

        # Requires self attributes above, put this at last
        self.ex = self.init_exchange(ex_id, ccxt_verbose)
        self.strategy = self.init_strategy(strategy_name)

        self.markets = self.ex.markets
        self.timeframes = self.ex.timeframes
        self.ohlcvs = self.create_empty_ohlcv_store()

        self._summary = {
            'start': None,
            'now': None,                # Update in getter
            'days': 0,                  # Update in getter
            'initial_balance': {},      # Update on first update_wallet
            'initial_value': 0,         # Update on first update_wallet after start trading (1m ohlcv are up-to-date)
            'current_balance': {},      # Update in getter
            'current_value': 0,         # Update in getter
            'total_trade_fee': 0,       # Update in getter (from past trades)
            'total_margin_fee': 0,      # Update in getter (from past trades)
            'PL': 0,                    # Update in getter
            'PL(%)': 0,                 # Update in getter
            'PL_Eff': 0,                # Update in getter
        }

    def init_exchange(self, ex_id, ccxt_verbose=False):
        """ Make an instance of a custom EX class. """
        key = load_keys(self._config['key_file'])[ex_id]
        ex_class = getattr(exchanges, str.capitalize(ex_id))
        return ex_class(self.mongo, key['apiKey'], key['secret'],
                        custom_config=self._config,
                        ccxt_verbose=ccxt_verbose,
                        log=self.log)

    def init_strategy(self, name):
        if name == 'pattern':
            strgy = strategy.PatternStrategy(self, self._config)
        else:
            raise ValueError(f"{name} strategy is not supported.")

        return strgy

    async def start(self):
        """ All-in-one entry for starting trading bot. """
        # Get required starting tasks of exchange.
        ex_start_tasks = self.ex.start_tasks()

        # Start routines required by exchange and trader itself
        await asyncio.gather(
            *ex_start_tasks,
            self._start()
        )

    async def _start(self):
        """ Starting entry for OnlineTrader. """
        await self.ex_ready()
        logger.info("Exchange is ready")

        await self.start_trading()

    async def ex_ready(self):
        while True:
            if self.ex.is_ready():
                return True
            else:
                await asyncio.sleep(2)

    async def start_trading(self):
        logger.info("Start trading...")
        self._summary['start'] = utc_now()

        for market in self.ex.markets:
            self.ex.set_market_start_dt(market, self._summary['start'])

        while True:
            # read latest ohlcv from db
            await self.update_ohlcv()

            await self.strategy.run()

            # wait til next minute
            # +45 sec to wait for ohlcv of all markets to be fetched
            countdown = roundup_dt(utc_now(), min=1) - utc_now()
            await asyncio.sleep(countdown.seconds + 45)

    async def update_ohlcv(self):

        async def build_recent_ohlcv():
            src_tf = '1m'

            # Build ohlcvs from 1m
            for market in self.markets:
                for tf in self.timeframes:
                    if tf != src_tf:
                        src_end_dt = await self.mongo.get_ohlcv_end(self.ex.exname, market, src_tf)
                        target_end_dt = await self.mongo.get_ohlcv_end(self.ex.exname, market, tf)
                        target_start_dt = target_end_dt - timeframe_timedelta(tf) * 5

                        # Build ohlcv starting from 5 bars earlier from latest bar
                        await build_ohlcv(self.mongo, self.ex.exname, market, src_tf, tf,
                                        start=target_start_dt, end=src_end_dt)

        await build_recent_ohlcv()

        # Get newest ohlcvs
        td = timedelta(days=self.config['strategy']['data_days'])
        end = roundup_dt(utc_now(), min=1)
        start = end - td
        self.ohlcvs = await self.mongo.get_ohlcvs_of_symbols(self.ex.exname, self.markets, self.timeframes, start, end)

        for symbol, tfs in self.ohlcvs.items():
            sm_tf = smallest_tf(list(self.ohlcvs[symbol].keys()))

            for tf in tfs:
                if tf != sm_tf:
                    self.ohlcvs[symbol][tf] = self.ohlcvs[symbol][tf][:-1] # drop the last row
            self.fill_ohlcv_with_small_tf(self.ohlcvs[symbol])

    async def long(self, symbol, confidence, type='market', scale_order=True):
        """ Cancel all orders, close sell positions
            and open a buy margin order (if has enough balance).
        """
        res = None
        if self.enable_trade:
            res = await self._do_long_short(
                'long', symbol, confidence, type, scale_order=scale_order)
        return res

    async def short(self, symbol, confidence, type='market', scale_order=True):
        """ Cancel all orders, close buy positions
            and open a sell margin order (if has enough balance).
        """
        res = None
        if self.enable_trade:
            res = await self._do_long_short(
                'short', symbol, confidence, type, scale_order=scale_order)
        return res

    async def _do_long_short(self, action, symbol, confidence, type='limit', scale_order=True):

        side = 'buy' if action == 'long' else 'sell'

        await self.cancel_all_orders(symbol)
        await self.ex.update_wallet()
        positions = await self.ex.fetch_positions()
        orderbook = await self.ex.get_orderbook(symbol)

        symbol_positions = filter_by(positions, ('symbol', symbol))

        symbol_amount = 0
        for pos in symbol_positions: # a symbol normally has only one position
            symbol_amount += pos['amount'] # negative amount means 'sell'

        # Calcualte position base value of all markets
        base, pl = self.calc_position_value(positions)
        self_base = base / self.config[self.ex.exname]['margin_rate']

        curr = symbol.split('/')[1]
        wallet_type = 'margin'

        # Calculate spendable balance
        cond = (symbol_amount >= 0) if action == 'long' else (symbol_amount <= 0)
        if cond:
            available_balance = self.ex.get_balance(curr, wallet_type)
            total_value = available_balance + self_base

        else:
            sym_base, sym_pl = self.calc_position_value(symbol_positions)
            self_sym_base = sym_base / self.config[self.ex.exname]['margin_rate']
            close_side = 'sell' if action == 'long' else 'buy'
            pos_close_fee = self.calc_position_close_fee(close_side, symbol_positions, orderbook)
            position_return = self_sym_base + sym_pl - pos_close_fee
            available_balance = self.ex.get_balance(curr, wallet_type) + position_return
            total_value = available_balance + self_base - self_sym_base  # substract overlap base of current symbol

        spendable = available_balance - total_value * self.config['maintain_portion']

        if spendable > 0:
            spend = spendable * abs(confidence) / 100 * self.config['trade_portion']

            trade_value = spend * self.config[self.ex.exname]['margin_rate']
            if trade_value < self.config[self.ex.exname]['min_trade_value']:
                logger.info(f"Trade value is < {self.config[self.ex.exname]['min_trade_value']}."
                            f"Skip the {side} order.")
                return None

            has_opposite_open_position = (symbol_amount < 0) if action == 'long' else (symbol_amount > 0)
            order_count = self.config['scale_order_count']

            if action == 'long':
                start_price = orderbook['bids'][0][0] * (1 - self.config['scale_order_near_percent'])
                close_end_price = orderbook['bids'][0][0] * (1 - self.config['scale_order_close_far_percent'])
                end_price = orderbook['bids'][0][0] * (1 - self.config['scale_order_far_percent'])
            else:
                start_price = orderbook['asks'][0][0] * (1 + self.config['scale_order_near_percent'])
                close_end_price = orderbook['bids'][0][0] * (1 + self.config['scale_order_close_far_percent'])
                end_price = orderbook['bids'][0][0] * (1 + self.config['scale_order_far_percent'])

            # Calculate amount to open, not including close amount (close amount == symbol_amount)
            amount = self.calc_order_amount(symbol, type, side, spend, orderbook,
                                            price=start_price, margin=True)

            orders = []
            min_value = self.config[self.ex.exname]['min_trade_value']

            if has_opposite_open_position:
                close_orders = self.gen_scale_orders(symbol, type, side, abs(symbol_amount),
                                                     start_price=start_price,
                                                     end_price=close_end_price,
                                                     order_count=order_count,
                                                     min_value=min_value)


                open_orders = self.gen_scale_orders(symbol, type, side, amount,
                                                    start_price=close_end_price,
                                                    end_price=end_price,
                                                    order_count=order_count,
                                                    min_value=min_value)

                orders = close_orders + open_orders

            else:
                open_orders = self.gen_scale_orders(symbol, type, side, amount,
                                                    start_price=start_price,
                                                    end_price=end_price,
                                                    order_count=order_count,
                                                    min_value=min_value)

                orders = open_orders


            res = None

            if type == 'limit' and scale_order:
                res = await self.ex.create_order_multi(orders)
            else:
                amount += abs(symbol_amount)
                res = await self.ex.create_order(symbol, type, side, amount, price=start_price)

            alert_sound(0.2, 'Order created', 3)

            if res:
                if isinstance(res, list):
                    price = 0
                    amount = 0

                    for order in res:
                        price += order['price'] * order['amount']
                        amount += order['amount']

                    price /= amount

                    logger.info(f"Created scaled margin {side} order: "
                                f"avg price: {price} amount: {amount} value: {price * amount}")

                else:
                    order = res
                    price = order['price']
                    amount = order['amount']
                    logger.info(f"Created margin {side} order: "
                                f"price: {price} amount: {amount} value: {price * amount}")

            elif res is None:
                logger.warn(f"Order is not submitted, uncomment the create_order line to enable.")

            return res

        else:
            logger.info(f"Spendable balance is < 0, unable to {action}.")

        return None

    @staticmethod
    def calc_position_value(positions):
        """ Summarize positions and return total base value and pl. """
        base = 0
        pl = 0

        for pos in positions:
            base += pos['base'] * abs(pos['amount'])
            pl += pos['pl']

        return base, pl

    def calc_position_close_fee(self, side, positions, orderbook):
        """ Estimate fees of closing positions base on orderbook.
            This assumes all positions are of same symbol.
        """
        def check_symbol(positions):
            sym = positions[0]['symbol']
            for pos in positions:
                if pos['symbol'] != sym:
                    raise ValueError("Positions must be the same symbol.")

        check_symbol(positions)
        symbol = positions[0]['symbol']

        amount = 0
        for pos in positions:
            if side == 'sell' and pos['amount'] < 0 \
            or side == 'buy'  and pos['amount'] > 0:
                amount += pos['amount']

        # If amount < 0 means 'sell' in previos margin orders, now need to buy from 'asks'.
        # If amount > 0 it's the opposite.
        book = orderbook['asks'] if amount < 0 else orderbook['bids']

        value = 0
        amount = abs(amount)
        for price, vol in book:
            remain = max(0, amount - vol)
            value += price * (amount - remain)
            amount = remain
            if remain <= 0:
                break

        curr = symbol.split('/')[0]
        fee = value * self.ex.trade_fees[curr]['taker_fees']
        return fee

    def calc_order_amount(self, symbol, type, side, balance, orderbook, price=None, margin=False):
        """ Stack orderbook price*volume to find amount the market can fill.
            Params
                market: str, 'limit', 'market' etc. (may support more in the future)
                side: str, side of this order, 'buy'/'sell'
                price: float, will not be used in 'market' order
                balance: float, balance to spend
                margin: bool
                orderbook: dict, contains 'asks' and 'bids'
        """
        amount = 0
        curr = symbol.split('/')[0]

        if margin:
            balance *= self.config[self.ex.exname]['margin_rate']

        if type == 'market':
            trade_fee = self.ex.trade_fees[curr]['taker_fees']
            book = orderbook['asks'] if side == 'buy' else orderbook['bids']
            for price, vol in book:
                remain = max(0, balance - price * vol)
                amount += (balance - remain) / price / (1 + trade_fee)
                balance = remain
                if remain <= 0:
                    break

        elif type == 'limit':
            trade_fee = self.ex.trade_fees[curr]['maker_fees']
            amount = balance / price / (1 + trade_fee)

        else:
            raise ValueError(f"Type {type} is not supported yet.")

        return amount

    async def cancel_all_orders(self, symbol):
        open_orders = await self.ex.fetch_open_orders(symbol)
        ids = []

        for order in open_orders:
            ids.append(order['id'])

        return await self.ex.cancel_order_multi(ids)

    def create_empty_ohlcv_store(self):
        """ ohlcv[ex][market][ft] """
        cols = ['timestamp', 'open', 'close', 'high', 'low', 'volume']
        ohlcv = {}

        df = pd.DataFrame(columns=cols)
        df.set_index('timestamp', inplace=True)

        # Each exchange has different timeframes
        for market in self.markets:
            ohlcv[market] = {}

            for tf in self.timeframes:
                ohlcv[market][tf] = df.copy(deep=True)

        return ohlcv

    @staticmethod
    def fill_ohlcv_with_small_tf(ohlcvs):
        """ Fill larger timeframe ohlcv with smaller ones
            to make larger timeframe real-time.
        """
        sm_tf = smallest_tf(list(ohlcvs.keys()))

        for tf in ohlcvs.keys():
            if tf != sm_tf:
                start_dt = ohlcvs[tf].index[-1] + timeframe_timedelta(tf)
                end_dt = ohlcvs[sm_tf].index[-1]

                # All timeframes are at the same timestamp, no need to fill
                if len(ohlcvs[sm_tf][start_dt:]) == 0:
                    continue

                new_ohlcv = ohlcvs[tf].iloc[0].copy()
                new_ohlcv.name = end_dt
                new_ohlcv.open = ohlcvs[sm_tf][start_dt:].iloc[0].open
                new_ohlcv.close = ohlcvs[sm_tf][start_dt:].iloc[-1].close
                new_ohlcv.high = ohlcvs[sm_tf][start_dt:].high.max()
                new_ohlcv.low = ohlcvs[sm_tf][start_dt:].low.min()
                new_ohlcv.volume = ohlcvs[sm_tf][start_dt:].volume.sum()

                ohlcvs[tf] = ohlcvs[tf].append(new_ohlcv)

        return ohlcvs

    def eval_summary(self):
        td = timedelta(seconds=self.config['summary_delay'])
        if (utc_now() - self._summary['now']) < td:
            return self._summary

        self.ex.update_wallet()

        wallet_value = self.ex.calc_wallet_value()
        now = utc_now()

        self._summary['now'] = now
        self._summary['days'] = (now - self._summary['start']).days
        self._summary['current_balance'] = self.wallet
        self._summary['current_value'] = wallet_value
        self._summary['total_trade_fee'] = self.ex.calc_trade_fee(self.start, now)
        self._summary['total_margin_fee'] = self.ex.calc_margin_fee(self.start, now)
        self._summary['PL'] = self._summary['current_value'] - self._summary['initial_value']
        self._summary['PL(%)'] = self._summary['PL'] / self._summary['initial_value']
        self._summary['PL_Eff'] = self._summary['PL(%)'] / days * 0.3


        self._summary = {
            'start': None,
            'now': None,                # Update in getter
            'days': 0,                  # Update in getter
            'initial_balance': {},      # Update on first update_wallet
            'initial_value': 0,         # Update on first update_wallet after start trading (1m ohlcv are up-to-date)
            'current_balance': {},      # Update in getter
            'current_value': 0,         # Update in getter
            'total_trade_fee': 0,       # Update in getter (from past trades)
            'total_margin_fee': 0,      # Update in getter (from past trades)
            'PL': 0,                    # Update in getter
            'PL(%)': 0,                 # Update in getter
            'PL_Eff': 0,                # Update in getter
        }

        return self._summary

    @staticmethod
    def gen_scale_orders(symbol, type, side, amount, start_price=0, end_price=0, order_count=20, min_value=0):
        """ Scale one order to multiple orders with different prices. """
        orders = []

        remaining_amount = amount
        amount_diff_base = amount / ((order_count + 1) * order_count / 2)

        cur_price = start_price
        dec = 100000000

        for i in range(order_count):
            cur_amount = amount_diff_base * (i + 1)
            cur_price *= random.randint(0.9999 * dec, 1.0001 * dec) / dec
            cur_amount *= random.randint(0.9999 * dec, 1.0001 * dec) / dec

            orders.append({
                "symbol": symbol,
                "type": type,
                "side": side,
                "amount": cur_amount,
                "price": cur_price,
            })

            if side == 'buy':
                cur_price = cur_price - abs(end_price - start_price) / order_count
            elif side == 'sell':
                cur_price = cur_price + abs(end_price - start_price) / order_count

        # Merge orders that have value < min_value
        idx = 0
        n_orders = len(orders)
        while idx < n_orders-1:

            if orders[idx]['price'] * orders[idx]['amount'] < min_value:
                cur_amount = orders[idx]['amount']
                cur_price = orders[idx]['price']
                merge_num = 1

                i = idx + 1
                while (cur_price / merge_num * cur_amount < min_value) \
                and (i < n_orders):
                    cur_price += orders[i]['price']
                    cur_amount += orders[i]['amount']
                    merge_num += 1
                    i += 1

                orders[idx]['price'] = cur_price / merge_num
                orders[idx]['amount'] = cur_amount

                for _ in range(idx+1, i):
                    del orders[idx+1]
                    n_orders -= 1

            idx += 1

        # If last order's value is < min_value,
        # distribute its amount to other orders proportionally
        idx = len(orders) - 1
        if idx > 0 \
        and orders[idx]['price'] * orders[idx]['amount'] < min_value:
            total_amount = 0
            for i in range(len(orders)-1):
                total_amount += orders[i]['amount']

            for i in range(len(orders)-1):
                orders[i]['amount'] += orders[idx]['amount'] / total_amount * orders[i]['amount']

            del orders[idx]

        return orders