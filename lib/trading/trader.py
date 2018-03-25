from asyncio import ensure_future
from collections import OrderedDict
from datetime import timedelta, datetime

import asyncio
import copy
import logging
import math
import numpy as np
import pandas as pd
import random

from trading import strategy
from trading import exchanges
from utils import \
    config, \
    load_keys, \
    utc_now, \
    roundup_dt, \
    filter_by, \
    smallest_tf, \
    tf_td, \
    MIN_DT, \
    execute_mongo_ops

from analysis.hist_data import build_ohlcv

logger = logging.getLogger('pyct')


class SingleEXTrader():

    def __init__(self, mongo, ex_id, strategy_name,
                 userid=None,
                 custom_config=None,
                 ccxt_verbose=False,
                 disable_trading=False,
                 disable_ohlcv_stream=False,
                 log=False,
                 log_sig=False):

        self.mongo = mongo
        self._config = custom_config if custom_config else config
        self.config = self._config['trading']
        self.enable_trading = not disable_trading
        self.log = log
        self.log_sig = log_sig

        # Requires self attributes above, put this at last
        self.userid = userid if userid else config['userid']
        self.ex = self.init_exchange(ex_id, ccxt_verbose,
            disable_ohlcv_stream=disable_ohlcv_stream)
        self.strategy = self.init_strategy(strategy_name)
        self.ohlcvs = self.create_empty_ohlcv_store()

        self.max_fund = self.config['max_fund']

        self.summary = {
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

        self.margin_order_queue = OrderedDict()

    def init_exchange(self, ex_id, ccxt_verbose=False, disable_ohlcv_stream=False):
        """ Make an instance of a custom EX class. """
        key = load_keys()[self.userid][ex_id]
        ex_class = getattr(exchanges, str.capitalize(ex_id))
        return ex_class(
            self.mongo,
            key['apiKey'],
            key['secret'],
            custom_config=self._config,
            ccxt_verbose=ccxt_verbose,
            log=self.log,
            disable_ohlcv_stream=disable_ohlcv_stream)

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

        async def _set_startup_status():
            self.summary['start'] = utc_now()
            self.summary['now'] = utc_now()

            for market in self.ex.markets:
                self.ex.set_market_start_dt(market, self.summary['start'])

            self.summary['initial_balance'] = copy.deepcopy(self.ex.wallet)
            self.summary['initial_value'] = await self.ex.calc_account_value()

        logger.info(f"Start trader with user: {self.userid}")

        if not self.enable_trading:
            logger.info("Trading disabled")

        await self.ex_ready()
        logger.info("Exchange is ready")

        await _set_startup_status()

        logger.info("Start trading...")
        await self.start_trading()

    async def ex_ready(self):
        while True:
            if self.ex.is_ready():
                return True
            else:
                await asyncio.sleep(2)

    async def start_trading(self):

        last_log_time = MIN_DT
        last_sig = {market: np.nan for market in self.ex.markets}

        while True:

            if await self.ex.is_ohlcv_uptodate():
                # Read latest ohlcv from db
                await self.update_ohlcv()
                await self.execute_margin_order_queue()
                sig = await self.strategy.run()

                if self.log_sig:
                    last_log_time, last_sig = self.log_signals(sig, last_log_time, last_sig)

            # Wait additional 50 sec for ohlcv of all markets to be fetched
            fetch_interval = timedelta(seconds=self.ex.config['ohlcv_fetch_interval'])
            countdown = roundup_dt(utc_now(), fetch_interval) - utc_now()
            await asyncio.sleep(countdown.seconds + 90)

    def log_signals(self, sig, last_log_time, last_sig):
        """ Log signal periodically or on signal change. """

        def sig_changed(sig, market):
            if (not np.isnan(sig[market].iloc[-1]) or not np.isnan(last_sig[market])) \
            and (sig[market].iloc[-1] != last_sig[market]):
                logger.debug(f"{market} signal changed from "
                             f"{last_sig[market]} to {sig[market].iloc[-1]}")
                last_sig[market] = sig[market].iloc[-1]
                return True

            return False

        if (utc_now() - last_log_time) > \
        tf_td(self.config['indicator_tf']) / 5:
            for market in self.ex.markets:
                logger.info(f"{market} indicator signal @ {utc_now()}\n{sig[market][-10:]}")

            last_log_time = utc_now()
        else:
            for market in self.ex.markets:
                if sig_changed(sig, market):
                    logger.info(f"{market} indicator signal @ {utc_now()}\n{sig[market][-10:]}")

        return last_log_time, last_sig

    async def update_ohlcv(self):

        async def build_recent_ohlcv():
            src_tf = '1m'

            # Build ohlcvs from 1m
            for market in self.ex.markets:
                for tf in self.ex.timeframes:
                    if tf != src_tf:
                        src_end_dt = await self.mongo.get_ohlcv_end(self.ex.exname, market, src_tf)
                        target_end_dt = await self.mongo.get_ohlcv_end(self.ex.exname, market, tf)
                        target_start_dt = target_end_dt - tf_td(tf) * 5

                        # Build ohlcv starting from 5 bars earlier from latest bar
                        await build_ohlcv(self.mongo, self.ex.exname, market, src_tf, tf,
                                        start=target_start_dt, end=src_end_dt)

        await build_recent_ohlcv()

        # Get newest ohlcvs
        td = timedelta(days=self.config['strategy']['data_days'])
        end = roundup_dt(utc_now(), timedelta(minutes=1))
        start = end - td
        self.ohlcvs = await self.mongo.get_ohlcvs_of_symbols(
            self.ex.exname, self.ex.markets, self.ex.timeframes, start, end)

        for symbol, tfs in self.ohlcvs.items():
            sm_tf = smallest_tf(list(self.ohlcvs[symbol].keys()))

            for tf in tfs:
                if tf != sm_tf:
                    self.ohlcvs[symbol][tf] = self.ohlcvs[symbol][tf][:-1] # drop the last row
            self.fill_ohlcv_with_small_tf(self.ohlcvs[symbol])

    async def long(self, symbol, confidence, type='limit', scale_order=True):
        """ Cancel all orders, close sell positions
            and open a buy margin order (if has enough balance).
        """
        res = None

        if not self.enable_trading:
            return True

        res = await self._do_long_short(
            'long', symbol, confidence, type, scale_order=scale_order)

        return True if res else False

    async def short(self, symbol, confidence, type='limit', scale_order=True):
        """ Cancel all orders, close buy positions
            and open a sell margin order (if has enough balance).
        """
        res = None

        if not self.enable_trading:
            return True

        res = await self._do_long_short(
            'short', symbol, confidence, type, scale_order=scale_order)

        return True if res else False

    async def close_position(self, symbol, confidence, type='limit', scale_order=True):
        res = None

        if not self.enable_trading:
            return True

        res = await self._do_long_short(
            'close', symbol, 100, type, scale_order=scale_order)

        return True if res else False


    async def _do_long_short(self, action, symbol, confidence,
                             type='limit',
                             scale_order=True):

        async def save_to_db(orders):
            if not isinstance(orders, list):
                orders = [orders]

            # Orders' group id to label orders that are created at the same time
            group_id = await self.mongo.get_last_order_group_id(self.ex.exname)
            group_id += 1

            collname = f"{self.ex.exname}_created_orders"
            coll = self.mongo.get_collection(
                self._config['database']['dbname_trade'], collname)

            ops = []
            for ord in orders:
                ord['group_id'] = group_id

                ops.append(
                    ensure_future(
                        coll.update_one(
                            {'id': ord['id']},
                            {'$set': ord},
                            upsert=True)))

            await execute_mongo_ops(ops)

        side = 'buy' if action == 'long' else 'sell'

        await self.cancel_all_orders(symbol)
        await self.ex.update_wallet()

        orders_value = await self.ex.calc_order_value()
        positions = await self.ex.fetch_positions()
        orderbook = await self.ex.get_orderbook(symbol)

        # Remove queued margin order
        if symbol in self.margin_order_queue:
            order = self.margin_order_queue[symbol]
            logger.debug(f"{symbol} {order['action']} margin order is removed from queue")
            self.dequeue_margin_order(symbol)

        symbol_positions = filter_by(positions, ('symbol', symbol))

        symbol_amount = 0
        for pos in symbol_positions: # a symbol normally has only one position
            symbol_amount += pos['amount'] # negative amount means 'sell'

        _action = None
        if action == 'close':
            # there's no position to close
            if symbol_amount == 0:
                return None

            _action = 'close'
            side = 'buy' if symbol_amount < 0 else 'sell'
            action = 'long' if side == 'buy' else 'short'

        # Calcualte position base value of all markets
        base_value, pl = self.calc_position_value(positions)
        self_base_value = base_value / self.config[self.ex.exname]['margin_rate']

        curr = symbol.split('/')[1]
        wallet_type = 'margin'

        prices = self.calc_three_point_prices(orderbook, action)

        amount = 0

        # Calculate order amount
        has_opposite_open_position = (symbol_amount < 0) if action == 'long' else (symbol_amount > 0)
        if has_opposite_open_position:
            # calculate amount to close position
            amount = abs(symbol_amount)
        else:
            # calculate amount to open position
            available_balance = self.ex.get_balance(curr, wallet_type)
            total_value = available_balance + self_base_value + orders_value

            # Cap max trading funds
            if total_value > self.max_fund:
                available_balance -= (total_value - self.max_fund)
                total_value = available_balance + self_base_value

            maintain_portion = total_value * self.config['maintain_portion']
            spendable = max(available_balance - maintain_portion, 0)
            spendable = min(spendable, (total_value - maintain_portion) * self.config['trade_portion'])

            if spendable > 0:
                spend = spendable * abs(confidence) / 100

                trade_value = spend * self.config[self.ex.exname]['margin_rate']
                if trade_value < self.config[self.ex.exname]['min_trade_value']:
                    logger.info(f"Trade value < {self.config[self.ex.exname]['min_trade_value']}."
                                f"Skip the {side} order.")
                    return None

                # Skip this action if there's already an open position that holds
                # more than 1/3 of total value.
                sym_base_value, sym_pl = self.calc_position_value(symbol_positions)
                if sym_base_value > total_value / 3:
                    logger.info(f"Skip {action} {symbol} because an {side} position is already open")
                    return None

            else:
                logger.info(f"Spendable balance is < 0, unable to {action} {symbol}")
                return None


            # Calculate amount to open, not including close amount (close amount == symbol_amount)
            amount = self.calc_order_amount(symbol, type, side, spend, orderbook,
                                            start_price=prices['start_price'],
                                            end_price=prices['end_price'],
                                            margin=True,
                                            scale_order=scale_order)

        res = None
        orders = []
        order_count = self.config['scale_order_count']

        if type == 'limit' and scale_order:
            if has_opposite_open_position:
                end_price = prices['close_end_price']
                exact_amount = True
            else:
                end_price = prices['end_price']
                exact_amount = False

            orders = self.gen_scale_orders(symbol, type, side, amount,
                                            start_price=prices['start_price'],
                                            end_price=end_price,
                                            max_order_count=order_count,
                                            exact_amount=exact_amount)

            res = await self.ex.create_order_multi(orders)

        else:
            res = await self.ex.create_order(symbol, type, side, amount, price=prices['start_price'])

        if res:
            await save_to_db(res)

            if has_opposite_open_position:
                reason = "Close old position"
            else:
                reason = "Open new position"

            logger.info(f"{reason}")

            if isinstance(res, list):
                price = 0
                amount = 0

                for order in res:
                    price += order['price'] * order['amount']
                    amount += order['amount']

                price /= amount

                logger.info(f"Created {symbol} scaled margin {side} order: "
                            f"avg price: {price} amount: {amount} value: {price * amount}")
            else:
                order = res
                price = order['price']
                amount = order['amount']
                logger.info(f"Created {symbol} margin {side} order: "
                            f"price: {price} amount: {amount} value: {price * amount}")

            # Queue open position if current action is to close position
            if has_opposite_open_position and not _action == 'close':
                self.queue_margin_order(action, symbol, confidence,
                                        type=type,
                                        scale_order=True)
        else:
            logger.error(f"Failed to create orders")

        return res

    def calc_three_point_prices(self, orderbook, action):
        prices = {}
        if action == 'long':
            prices['start_price'] = orderbook['bids'][0][0] * (1 - self.config['scale_order_near_percent'])
            prices['close_end_price'] = orderbook['bids'][0][0] * (1 - self.config['scale_order_close_far_percent'])
            prices['end_price'] = orderbook['bids'][0][0] * (1 - self.config['scale_order_far_percent'])
        else:
            prices['start_price'] = orderbook['asks'][0][0] * (1 + self.config['scale_order_near_percent'])
            prices['close_end_price'] = orderbook['bids'][0][0] * (1 + self.config['scale_order_close_far_percent'])
            prices['end_price'] = orderbook['bids'][0][0] * (1 + self.config['scale_order_far_percent'])
        return prices

    @staticmethod
    def calc_position_value(positions):
        """ Summarize positions and return total base value and pl. """
        base_value = 0
        pl = 0

        for pos in positions:
            base_value += pos['base_price'] * abs(pos['amount'])
            pl += pos['pl']

        return base_value, pl

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

    def calc_order_amount(self, symbol, type, side, balance, orderbook,
                          start_price=None,
                          end_price=None,
                          margin=False,
                          scale_order=False):
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
        trade_fee = 0
        curr = symbol.split('/')[0]

        if margin:
            balance *= self.config[self.ex.exname]['margin_rate']

        if type == 'market':
            trade_fee = self.ex.trade_fees[curr]['taker_fees']
        elif type == 'limit':
            trade_fee = self.ex.trade_fees[curr]['maker_fees']

        price = start_price

        if type == 'market':
            book = orderbook['asks'] if side == 'buy' else orderbook['bids']
            for price, vol in book:
                remain = max(0, balance - price * vol)
                amount += (balance - remain) / price / (1 + trade_fee)
                balance = remain
                if remain <= 0:
                    break

        elif type == 'limit':
            amount = balance / price / (1 + trade_fee)

        else:
            raise ValueError(f"Type {type} is not supported yet.")


        if scale_order:
            Pmin = min(start_price, end_price)
            Pmax = max(start_price, end_price)
            Pd = Pmax - Pmin

            if side == 'buy':
                amount /= 1 - Pd/2/Pmax
            else:
                amount /= 1 + Pd/2/Pmin

        return amount

    def queue_margin_order(self, action, symbol, confidence, type, scale_order):
        self.margin_order_queue[symbol] = {
            'action': action,
            'symbol': symbol,
            'confidence': confidence,
            'type': type,
            'scale_order': scale_order,
        }

    def dequeue_margin_order(self, symbol):
        if symbol in self.margin_order_queue:
            del self.margin_order_queue[symbol]

    async def execute_margin_order_queue(self):
        if not self.margin_order_queue:
            return None

        positions = self.ex.fetch_positions()

        for symbol, order in self.margin_order_queue.items():
            symbol_pos = filter_by(positions, ('symbol', symbol))

            if not symbol_pos: # if symbol_pos is [] means there's no open position
                order = self.margin_order_queue[symbol]
                self.dequeue_margin_order(symbol)
                act = self.long if order['action'] == 'long' else self.short
                act(order['symbol'], order['confidence'], order['type'], order['scale_order'])

    async def cancel_all_orders(self, symbol):
        if not self.enable_trading:
            return {}

        open_orders = await self.ex.fetch_open_orders(symbol)
        ids = []

        for order in open_orders:
            if order['symbol'] == symbol:
                ids.append(order['id'])

        return await self.ex.cancel_order_multi(ids)

    def create_empty_ohlcv_store(self):
        """ ohlcv[ex][market][ft] """
        cols = ['timestamp', 'open', 'close', 'high', 'low', 'volume']
        ohlcv = {}

        df = pd.DataFrame(columns=cols)
        df.set_index('timestamp', inplace=True)

        # Each exchange has different timeframes
        for market in self.ex.markets:
            ohlcv[market] = {}

            for tf in self.ex.timeframes:
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
                start_dt = ohlcvs[tf].index[-1] + tf_td(tf)
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

    async def get_summary(self):
        td = timedelta(seconds=self.config['summary_delay'])
        if (utc_now() - self.summary['now']) < td:
            return self.summary

        await self.ex.update_wallet()
        await self.ex.update_my_trades()

        start = self.summary['start']
        now = utc_now()

        self.summary['now'] = now
        self.summary['days'] = (now - start).seconds / 60 / 60 / 24
        self.summary['#profit_trades'] = 0
        self.summary['#loss_trades'] = 0
        self.summary['current_balance'] = copy.deepcopy(self.ex.wallet)
        self.summary['current_value'] = await self.ex.calc_account_value()
        self.summary['total_trade_fee'] = await self.ex.calc_trade_fee(start, now)
        self.summary['total_margin_fee'] = self.ex.calc_margin_fee(start, now)
        self.summary['PL'] = self.summary['current_value'] - self.summary['initial_value']
        self.summary['PL(%)'] = self.summary['PL'] / self.summary['initial_value'] * 100
        self.summary['PL_Eff'] = self.summary['PL(%)'] / self.summary['days'] * 0.3

        return self.summary

    def gen_scale_orders(self, symbol, type, side, amount,
                         start_price=0,
                         end_price=0,
                         max_order_count=20,
                         exact_amount=False):
        """ Scale one order to multiple orders with different prices. """
        orders = []

        min_amount = self.ex.markets_info[symbol]['limits']['amount']['min']
        order_count = min(int(math.sqrt(2 * amount / min_amount) - 1), max_order_count)
        order_count = max(order_count, 1)
        print('order_count:', order_count)
        amount_diff_base = amount / ((order_count + 1) * order_count / 2)
        cur_price = start_price
        dec = 100000000

        for i in range(order_count):
            cur_amount = amount_diff_base * (i + 1)
            cur_price *= random.randint(0.9999 * dec, 1.0001 * dec) / dec

            if not exact_amount:
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

        # Merge orders to make amount >= min_amount
        idx = 0
        n_orders = len(orders)
        while idx < n_orders-1:
            if orders[idx]['amount'] < min_amount:
                print('merge')
                cur_amount = orders[idx]['amount']
                cur_price = orders[idx]['price']
                merge_num = 1

                i = idx + 1
                while (cur_amount < min_amount) \
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

        # If last order's amount < min_amount,
        # distribute its amount to other orders proportionally
        idx = len(orders) - 1
        if idx > 0 \
        and orders[idx]['price'] * orders[idx]['amount'] < min_amount:
            total_amount = 0
            for i in range(len(orders)-1):
                total_amount += orders[i]['amount']

            for i in range(len(orders)-1):
                orders[i]['amount'] += orders[idx]['amount'] / total_amount * orders[i]['amount']

            del orders[idx]

        return orders

    def add_market(self, market):
        pass
        # for market in self.ex.markets:
        #     # New market is added
        #     if market not in self.ex.markets_start_dt:
        #         self.ex.set_market_start_dt(market, utc_now())
        #         self.reset_orders

    def remove_market(self, market):
        pass
