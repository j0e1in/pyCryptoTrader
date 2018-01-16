from datetime import timedelta
from pprint import pprint
import asyncio
import logging
import pandas as pd

from trading import exchanges
from utils import config, \
                  load_keys, \
                  utc_now, \
                  rounddown_dt, \
                  roundup_dt, \
                  filter_by

from ipdb import set_trace as trace

logger = logging.getLogger()


class SingleEXTrader():

    def __init__(self, mongo, ex_id, strategy, custom_config=None, verbose=False):
        self.mongo = mongo
        self.strategy = strategy
        self.verbose = verbose
        self._config = custom_config if custom_config else config
        self.config = self._config['trading']

        # Requires self attributes above, put this at last
        self.ex = self.init_exchange(ex_id)
        self.markets = self.ex.markets
        self.timeframes = self.ex.timeframes
        self.ohlcv = self.create_empty_ohlcv_store()

    def init_exchange(self, ex_id):
        key = load_keys(self._config['key_file'])[ex_id]
        ex_class = getattr(exchanges, str.capitalize(ex_id))
        return ex_class(self.mongo, key['apiKey'], key['secret'],
                        custom_config=self._config,
                        verbose=self.verbose)

    async def start(self):
        """ All-in-one entry for starting trading bot. """
        # Get required starting tasks of exchange.
        ex_start_tasks = self.ex.start_tasks(log=self.verbose)

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

        while True:
            # read latest ohlcv from db
            await self.update_ohlcv()

            self.strategy.run()

            # wait til next minute
            # +45 sec to wait for ohlcv of all markets to be fetched
            countdown = roundup_dt(utc_now(), min=1) - utc_now()
            await asyncio.sleep(countdown.seconds + 45)

    async def update_ohlcv(self):
        td = timedelta(days=self.config['strategy']['ohlcv_days'])
        end = roundup_dt(utc_now(), min=1)
        start = end - td
        self.ohlcv = await self.mongo.get_ohlcvs_of_symbols(self.ex.exname, self.markets, self.timeframes, start, end)

    async def long(self, symbol, confidence, type='market'):
        """ Cancel all orders, close sell positions
            and open a buy margin order (if has enough balance).
        """
        await self._do_long_short('long', symbol, confidence, type)

    async def short(self, symbol, confidence, type='market'):
        """ Cancel all orders, close buy positions
            and open a sell margin order (if has enough balance).
        """
        await self._do_long_short('short', symbol, confidence, type)

    async def _do_long_short(self, action, symbol, confidence, type='market'):

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
            spend = spendable * confidence / 100 * self.config['trade_portion']

            trade_value = spend * self.config[self.ex.exname]['margin_rate']
            if trade_value < self.config[self.ex.exname]['min_trade_value']:
                logger.info(f"Trade value is lower than minimum. Skip long order.")
                return

            if action == 'long':
                price = orderbook['bids'][0][0] * (1 - self.config['limit_price_diff'])
            else:
                price = orderbook['asks'][0][0] * (1 + self.config['limit_price_diff'])

            side = 'buy' if action == 'long' else 'sell'
            amount = self.calc_order_amount(symbol, type, side, spend, orderbook,
                                            price=price, margin=True)

            cond = (symbol_amount < 0) if action == 'long' else (symbol_amount > 0)
            if cond:
                amount += abs(symbol_amount)  # plus the opposite side position amount

            order = await self.ex.create_order(symbol, type, side, amount, price=price)
            if order:
                logger.info(f"Created an margin {side} order: "
                            f"id: {order['id']} price: {order['price']} amount: {order['amount']}")
        else:
            logger.info(f"Spendable balance is < 0, unable to {action}.")

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
