from asyncio import ensure_future
from collections import OrderedDict
from concurrent.futures import FIRST_COMPLETED
from datetime import timedelta

import asyncio
import copy
import concurrent
import logging
import math
import numpy as np
import pandas as pd
import random

from api import APIServer
from api.notifier import Messenger
from db import Datastore
from trading.indicators import Indicator
from trading.strategy import PatternStrategy, Signals
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
    execute_mongo_ops, \
    async_catch_traceback, \
    is_price_valid

logger = logging.getLogger('pyct')


class SingleEXTrader():

    ds_list = [
        'enable_trading', 'max_fund', 'summary', 'margin_order_queue', 'ohlcv_up'
    ]

    def __init__(self, mongo, ex_id, strategy,
                 uid=None,
                 custom_config=None,
                 ccxt_verbose=False,
                 disable_trading=False,
                 disable_ohlcv_stream=False,
                 disable_notification=False,
                 log=False,
                 log_sig=False,
                 reset_state=False,
                 notify_start=True):

        self._config = custom_config or config
        self.uid = uid if uid else self._config['uid']
        self.ds = Datastore.create(f"{self.uid}:trader")

        if reset_state:
            logger.debug(f"Reset state of {self.uid}-{ex_id}")
            self.ds.clear()

        self.config = self._config['trading']
        self.mongo = mongo
        self.enable_trading = self.ds.get('enable_trading', not disable_trading)
        self.log = log
        self.log_sig = log_sig
        self.notify_start = notify_start
        self._stop = False

        # Requires self attributes above
        # Order of this initialization matters
        self.notifier = Messenger(self, self._config, disable=disable_notification)
        self.ex = self.init_exchange(ex_id,
            notifier=self.notifier,
            ccxt_verbose=ccxt_verbose,
            disable_ohlcv_stream=disable_ohlcv_stream,
            reset_state=reset_state)
        self.strategy = self.init_strategy(strategy)
        self.ohlcvs = self.create_empty_ohlcv_store()
        self.ohlcv_up = self.ds.get('ohlcv_up', True)

        self.margin_order_queue = self.ds.get('margin_order_queue', OrderedDict())
        self.max_fund = self.ds.get('max_fund', self.config['max_fund'])
        self.summary = self.ds.get('summary', {
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
        })

    def init_exchange(self,
                      ex_id,
                      notifier=None,
                      ccxt_verbose=False,
                      disable_ohlcv_stream=False,
                      reset_state=False):
        """ Make an instance of a custom EX class. """
        key = load_keys()[self.uid][ex_id]
        ex_class = getattr(exchanges, str.capitalize(ex_id))
        return ex_class(
            self.mongo,
            uid=self.uid,
            apikey=key['apiKey'],
            secret=key['secret'],
            custom_config=self._config,
            ccxt_verbose=ccxt_verbose,
            log=self.log,
            notifier=notifier,
            disable_ohlcv_stream=disable_ohlcv_stream,
            reset_state=reset_state)

    def init_strategy(self, name):
        if name == 'pattern':
            strgy = PatternStrategy(self, self._config)
        else:
            raise ValueError(f"{name} strategy is not supported.")

        return strgy

    async def start(self):
        """ All-in-one entry for starting trading bot. """

        async def cleanup(pending):
            await self.ex.ex.close()
            for task in pending:
                task.cancel()

        # Get required starting tasks of exchange.
        ex_start_tasks = self.ex.start_tasks()

        # Start routines required by exchange and trader itself
        done, pending = await asyncio.wait(
            [
                *ex_start_tasks,
                self._start(),
                self.check_position_status(),
                self.ds.sync_routine(self.ds_list, self),
                self.ex.ds.sync_routine(self.ex.ds_list, self.ex),
                self.strategy.ds.sync_routine(self.strategy.ds_list, self.strategy)
            ],
            return_when=FIRST_COMPLETED)

        end = False
        while not end:
            for task in done:

                # The trader stopped
                if task._coro.__name__ == '_start':
                    if self._stop:
                        await cleanup(pending)
                        return
                    else:
                        try:
                            exp = task.exception()
                        except concurrent.futures.TimeoutError:
                            logger.warning(f"Task exception timeout")
                        else:
                            # Close ex before trader stops
                            await cleanup(pending)
                            raise exp
            if not end:
                done, pending = await asyncio.wait(pending,
                    return_when=FIRST_COMPLETED)

    def stop(self):
        self._stop = True

    async def _start(self):
        """ Starting entry for OnlineTrader. """

        async def _set_startup_status():
            self.summary['start'] = utc_now()
            self.summary['now'] = utc_now()
            self.summary['initial_balance'] = copy.deepcopy(self.ex.wallet)
            self.summary['initial_value'] = await self.ex.calc_account_value()

        logger.info(f"Start trader: {self.uid}")

        if not self.enable_trading:
            logger.info("Trading disabled")

        await self.wait_ex_to_be_ready()
        logger.info("Exchange is ready")

        if not self.summary['start']:
            await _set_startup_status()

        for market in self.ex.markets:
            self.ex.set_market_start_dt(market, self.summary['start'])

        if self.notify_start \
        and self.uid in self._config['apiclient']['notify_start_uid']:
            await self.notifier.notify_start()

        logger.info("Start trading")
        await self.start_trading()

    async def wait_ex_to_be_ready(self):
        while True:
            if self.ex.is_ready():
                return True
            else:
                await asyncio.sleep(2)

    async def start_trading(self):

        last_log_time = MIN_DT
        last_sig = {market: np.nan for market in self.ex.markets}
        self.ohlcvs = await self.mongo.get_latest_ohlcvs(
            self.ex.exname,
            self.ex.markets,
            self.ex.timeframes)

        while not self._stop:
            if await self.ex.is_ohlcv_uptodate():
                # Read latest ohlcv from db
                self.ohlcvs = await self.mongo.get_latest_ohlcvs(
                    self.ex.exname,
                    self.ex.markets,
                    self.ex.timeframes)

                await self.execute_margin_order_queue()
                sig = await self.strategy.run()

                if not self.ohlcv_up:
                    await self.notifier.notify_msg("Ohlcv stream is up")
                    self.ohlcv_up = True

                if self.log_sig:
                    last_log_time, last_sig = self.log_signals(sig, last_log_time, last_sig)
            else:
                if self.ohlcv_up and not await self.check_ohlcv_is_updating():
                    self.ohlcv_up = False
                    await self.notifier.notify_msg("Ohlcv stream is down")

            # Wait additional 90 sec for ohlcv of all markets to be fetched
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

        cur_time = utc_now()
        time_str = cur_time.strftime("%Y-%m-%d %H:%M:%S")
        log_remain_time = False

        if (cur_time - last_log_time) > \
        tf_td(self.config['indicator_tf']) / 8:
            for market in self.ex.markets:
                logger.info(f"{market} indicator signal @ {time_str}\n{sig[market][-20:]}")
                last_sig[market] = sig[market].iloc[-1]

            last_log_time = cur_time
            log_remain_time = True
        else:
            for market in self.ex.markets:
                if sig_changed(sig, market):
                    logger.info(f"{market} indicator signal @ {time_str}\n{sig[market][-20:]}")
                    log_remain_time = True

        if log_remain_time:
            td = tf_td(self.config['indicator_tf'])

            remaining_time = roundup_dt(utc_now(), td) - utc_now() # - td / self.config['strategy']['near_end_ratio']
            remaining_time -= timedelta(microseconds=remaining_time.microseconds)
            logger.info(f"{remaining_time} left to start trading")

        return last_log_time, last_sig

    async def long(self, symbol, confidence,
                   type='limit',
                   scale_order=True,
                   start_price=None,
                   end_price=None,
                   spend=None):
        """ Cancel all orders, close sell positions
            and open a buy margin order (if has enough balance).
        """
        res = None

        if not self.enable_trading:
            return {}

        res = await self._do_long_short_close_immediately(
            'long', symbol, confidence, type,
            scale_order=scale_order,
            start_price=start_price,
            end_price=end_price,
            to_spend=spend)

        return res

    async def short(self, symbol, confidence,
                   type='limit',
                   scale_order=True,
                   start_price=None,
                   end_price=None,
                   spend=None):
        """ Cancel all orders, close buy positions
            and open a sell margin order (if has enough balance).
        """
        res = None

        if not self.enable_trading:
            return {}

        res = await self._do_long_short_close_immediately(
            'short', symbol, confidence, type,
            scale_order=scale_order,
            start_price=start_price,
            end_price=end_price,
            to_spend=spend)

        return res

    async def close_position(self, symbol,
                            type='limit',
                            scale_order=True,
                            start_price=None,
                            end_price=None,
                            spend=None):
        res = None

        if not self.enable_trading:
            return {}

        if type == 'limit':
            res = await self._do_long_short(
                'close', symbol, 0, type,
                scale_order=scale_order,
                start_price=start_price,
                end_price=end_price,
                to_spend=spend)

        elif type == 'market':
            res = await self._do_long_short_close_immediately(
                'close', symbol, 0, type,
                scale_order=scale_order,
                start_price=start_price,
                end_price=end_price,
                to_spend=spend)

        else:
            raise ValueError(f"Unsupported type: {type}")

        return res

    async def _do_long_short(self, action, symbol, confidence,
                             type='limit',
                             scale_order=True,
                             start_price=None,
                             end_price=None,
                             to_spend=None):

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

        # Remove queued margin order because a new action is produced
        if symbol in self.margin_order_queue:
            order = self.margin_order_queue[symbol]
            logger.debug(f"{symbol} {order['action']} margin order is removed from queue")
            self.dequeue_margin_order(symbol)

        positions = await self.ex.fetch_positions()
        symbol_positions = filter_by(positions, ('symbol', symbol))

        symbol_amount = 0
        for pos in symbol_positions: # a symbol normally has only one position
            symbol_amount += pos['amount'] # negative amount means 'sell'

        side = 'buy' if action == 'long' else 'sell'

        orig_action = None
        if action == 'close':
            # there's no position to close
            if symbol_amount == 0:
                return None

            orig_action = 'close'
            side = 'buy' if symbol_amount < 0 else 'sell'
            action = 'long' if side == 'buy' else 'short'
        else:
            orig_action = action

        if not is_price_valid(start_price, end_price, side):
            logger.warning(f"prices are invalid: {start_price}, {end_price}, {side}")
            return None

        await self.cancel_all_orders(symbol)
        await self.ex.update_wallet()
        orders_value = await self.ex.calc_order_value()
        orderbook = await self.ex.get_orderbook(symbol)

        # Calcualte position base value of all markets
        base_value, pl = self.calc_position_value(positions)
        self_base_value = base_value / self.config[self.ex.exname]['margin_rate']

        curr = symbol.split('/')[1]
        wallet_type = 'margin'
        prices = self.calc_three_point_prices(orderbook, action)
        amount = 0

        # Calculate order amount
        has_opposite_open_position = (symbol_amount < 0) if action == 'long' else (symbol_amount > 0)

        # vairables for scale orders
        start_price = start_price or prices['start_price']
        if has_opposite_open_position or orig_action == 'close':
            end_price = end_price or prices['close_end_price']
            exact_amount = True
        else:
            end_price = end_price or prices['end_price']
            exact_amount = False

        if has_opposite_open_position or orig_action == 'close':
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
            trade_portion = (1 / max(len(self.ex.markets), 1)) * self.config['trade_portion']
            spendable = max(available_balance - maintain_portion, 0)
            spendable = min(spendable, (total_value - maintain_portion) * trade_portion)

            if spendable > 0:
                if to_spend and to_spend < available_balance - maintain_portion:
                    spend = to_spend
                else:
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
                                            start_price=start_price,
                                            end_price=end_price,
                                            margin=True,
                                            scale_order=scale_order)
        res = None
        orders = []
        order_count = self.config['scale_order_count']

        if type == 'limit' and scale_order:
            orders = self.gen_scale_orders(symbol, type, side, amount,
                                            start_price=start_price,
                                            end_price=end_price,
                                            max_order_count=order_count,
                                            exact_amount=exact_amount)

            res = await self.ex.create_order_multi(orders)

        else:
            res = await self.ex.create_order(symbol, type, side, amount, price=start_price)

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
                            f"avg price: {price} amount: {amount} value: {price * amount:0.2f}")
            else:
                order = res
                price = order['price']
                amount = order['amount']
                logger.info(f"Created {symbol} margin {side} order: "
                            f"price: {price} amount: {amount} value: {price * amount:0.2f}")

            # Queue open position if current action is to close position
            if has_opposite_open_position and not orig_action == 'close':
                logger.debug(f"Queue margin order: {action} {symbol}")
                self.queue_margin_order(action, symbol, confidence,
                                        type=type,
                                        scale_order=True)
        else:
            logger.error(f"Failed to create orders")

        return res

    async def _do_long_short_close_immediately(self, action, symbol, confidence,
                                               type='limit',
                                               scale_order=True,
                                               start_price=None,
                                               end_price=None,
                                               to_spend=None):
        """ Same as _do_long_short except this function closes
            existing positions with market orders.
        """

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
                            {
                                'id': ord['id']
                            }, {'$set': ord}, upsert=True)))

            await execute_mongo_ops(ops)

        positions = await self.ex.fetch_positions()
        symbol_positions = filter_by(positions, ('symbol', symbol))

        symbol_amount = 0
        for pos in symbol_positions:  # a symbol normally has only one position
            symbol_amount += pos['amount']  # negative amount means 'sell'

        side = 'buy' if action == 'long' else 'sell'

        orig_action = None
        if action == 'close':
            # there's no position to close
            if symbol_amount == 0:
                return None

            orig_action = 'close'
            side = 'buy' if symbol_amount < 0 else 'sell'
            action = 'long' if side == 'buy' else 'short'
        else:
            orig_action = action

        if not is_price_valid(start_price, end_price, side):
            logger.warning(f"prices are invalid: {start_price}, {end_price}, {side}")
            return None

        await self.cancel_all_orders(symbol)
        await self.ex.update_wallet()
        orders_value = await self.ex.calc_order_value()

        # Calcualte position base value of all markets
        base_value, pl = self.calc_position_value(positions)
        self_base_value = base_value / self.config[self.ex.exname]['margin_rate']

        curr = symbol.split('/')[1]
        wallet_type = 'margin'
        amount = 0

        # Close symbol's active opposite position
        has_opposite_open_position = (symbol_amount < 0) if action == 'long' else (symbol_amount > 0)

        # vairables for scale orders
        start_price = start_price or prices['start_price']
        end_price = end_price or prices['end_price']
        exact_amount = False

        if has_opposite_open_position or orig_action == 'close':
            res = await self.ex.close_position(symbol)
            logger.debug(f"Closed {symbol} position")

            if orig_action == 'close':
                return res

            # wait for exchange to update wallet
            await asyncio.sleep(10)
            await self.ex.update_wallet()

            # Re-fetch positions because some positions are closed
            positions = await self.ex.fetch_positions()
            base_value, pl = self.calc_position_value(positions)
            self_base_value = base_value / self.config[self.ex.exname]['margin_rate']

        # calculate amount to open position
        available_balance = self.ex.get_balance(curr, wallet_type)
        total_value = available_balance + self_base_value + orders_value

        # Cap max trading funds
        if total_value > self.max_fund:
            available_balance -= (total_value - self.max_fund)
            total_value = available_balance + self_base_value

        maintain_portion = total_value * self.config['maintain_portion']
        trade_portion = (1 / max(len(self.ex.markets), 1)) * self.config['trade_portion']
        spendable = max(available_balance - maintain_portion, 0)
        spendable = min(spendable, (total_value - maintain_portion) * trade_portion)

        if spendable > 0:
            if to_spend and to_spend < available_balance - maintain_portion:
                spend = to_spend
            else:
                spend = spendable * abs(confidence) / 100

            trade_value = spend * self.config[self.ex.exname]['margin_rate']

            if trade_value < self.config[self.ex.exname]['min_trade_value']:
                logger.info(
                    f"Trade value < {self.config[self.ex.exname]['min_trade_value']}."
                    f"Skip the {side} order.")
                return None

        else:
            logger.info(
                f"Spendable balance is < 0, unable to {action} {symbol}")
            return None

        orderbook = await self.ex.get_orderbook(symbol)
        prices = self.calc_three_point_prices(orderbook, action)

        # Calculate amount to open, not including close amount (close amount == symbol_amount)
        amount = self.calc_order_amount(symbol, type, side, spend, orderbook,
                                        start_price=start_price,
                                        end_price=end_price,
                                        margin=True,
                                        scale_order=scale_order)

        res = None
        orders = []
        order_count = self.config['scale_order_count']

        if type == 'limit' and scale_order:
            orders = self.gen_scale_orders(symbol, type, side, amount,
                                           start_price=start_price,
                                           end_price=end_price,
                                           max_order_count=order_count,
                                           exact_amount=exact_amount)

            res = await self.ex.create_order_multi(orders)

        else:
            res = await self.ex.create_order(
                symbol, type, side, amount, price=start_price)
        if res:
            await save_to_db(res)

            reason = f"Opened {symbol} position"
            logger.info(f"{reason}")

            if isinstance(res, list):
                price = 0
                amount = 0

                for order in res:
                    price += order['price'] * order['amount']
                    amount += order['amount']

                price /= amount

                logger.info(
                    f"Created {symbol} scaled margin {side} order: "
                    f"avg price: {price} amount: {amount} value: {price * amount:0.2f}"
                )
            else:
                order = res
                price = order['price']
                amount = order['amount']
                logger.info(
                    f"Created {symbol} margin {side} order: "
                    f"price: {price} amount: {amount} value: {price * amount:0.2f}"
                )
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

        positions = await self.ex.fetch_positions()

        for symbol, order in self.margin_order_queue.items():
            symbol_pos = filter_by(positions, ('symbol', symbol))

            if not symbol_pos: # if symbol_pos is [] means there's no open position
                order = self.margin_order_queue[symbol]
                self.dequeue_margin_order(symbol)
                act = self.long if order['action'] == 'long' else self.short
                await act(order['symbol'], order['confidence'], order['type'], order['scale_order'])

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
        self.summary['order_value'] = await self.ex.calc_order_value()
        self.summary['position_value'] = await self.ex.calc_all_position_value()
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
        if market in self.ex.markets:
            return False

        self.ex.markets.append(market)
        self.ex.ds.markets = self.ex.markets # save to redis immediately
        return True

    def remove_market(self, market):
        if not market in self.ex.markets:
            return False

        self.ex.markets.remove(market)
        self.ex.ds.markets = self.ex.markets # save to redis immediately
        return True

    async def check_ohlcv_is_updating(self):
        """ Check if all ohlcvs are older by more than 5 * ohlcv_fetch_interval. """
        await self.ex.update_ohlcv_start_end()

        td = timedelta(seconds=self.ex.config['ohlcv_fetch_interval'] * 5)

        for market in self.ex.markets:
            end = self.ex.ohlcv_start_end[market]['1m']['end']
            cur_time = utc_now()

            if cur_time - end < td:
                return True

        return False

    async def check_position_status(self):
        """ Check if any position is in danger or matches large PL(%) """
        margin_rate = self.config[self.ex.exname]['margin_rate']
        pos_large_pl = self.ds.get('pos_large_pl', {})
        pos_danger_pl = self.ds.get('pos_danger_pl', {})

        while True:
            positions = await self.ex.fetch_positions()
            pos_ids = [p['id'] for p in positions]

            # Log
            for pos in positions:
                base_value = pos['base_price'] * abs(pos['amount'])
                pl_perc = pos['pl'] * margin_rate / base_value * 100
                side = 'buy' if pos['amount'] > 0 else 'sell'
                logger.debug(f"Active position {self.uid} -- {pos['symbol']}, "
                             f"ID: {pos['id']}, side: {side}, PL: {pos['pl']:0.2f} "
                             f"PL(%): {pl_perc:0.2f} %")

                # Force to close partially filled positions
                # which remains a very small amount
                if pl_perc > 100 or pl_perc < -100:
                    logger.debug(f"Closing leftover position: {pos['symbol']}")
                    await self.close_position(pos['symbol'], type='market')

            # Remove closed positions
            to_del = []
            for id in pos_large_pl:
                if id not in pos_ids:
                    to_del.append(id)

            for id in to_del:
                del pos_large_pl[id]

            # Remove closed positions
            to_del = []
            for id in pos_danger_pl:
                if id not in pos_ids:
                    to_del.append(id)

            for id in to_del:
                del pos_danger_pl[id]

            # Add new positions
            for pos in positions:
                # Initialize first time added position
                if pos['id'] not in pos_large_pl:
                    pos_large_pl[pos['id']] = {
                        'last_notify_perc': None,
                        'pos': pos
                    }
                else: # Update old position
                    pos_large_pl[pos['id']]['pos'] = pos

                if pos['id'] not in pos_danger_pl:
                    pos_danger_pl[pos['id']] = {
                        'last_notify_perc': None,
                        'pos': pos
                    }
                else:
                    pos_danger_pl[pos['id']]['pos'] = pos

            # notify_position_large_pl
            for id, pos in pos_large_pl.items():
                base_value = pos['pos']['base_price'] * abs(pos['pos']['amount'])
                pl_perc = pos['pos']['pl'] * margin_rate / base_value * 100

                # Percentage meets threshold
                if pl_perc >= self._config['apiclient']['large_pl_threshold']:

                    # If has not been notified or percentage change > N%
                    if not pos['last_notify_perc'] \
                    or abs(pl_perc - pos['last_notify_perc']) >= \
                    self._config['apiclient']['large_pl_diff']:
                        await self.notifier.notify_position_large_pl(pos['pos'])
                        pos['last_notify_perc'] = pl_perc

            # notify_position_danger_pl
            for id, pos in pos_danger_pl.items():
                base_value = pos['pos']['base_price'] * abs(pos['pos']['amount'])
                pl_perc = -pos['pos']['pl'] / base_value * 100

                # Percentage meets threshold
                if pl_perc >= self._config['apiclient']['danger_pl_threshold']:

                    # If has not been notified or percentage change > N%
                    if not pos['last_notify_perc'] \
                    or abs(pl_perc - pos['last_notify_perc']) >= \
                    self._config['apiclient']['danger_pl_diff']:
                        await self.notifier.notify_position_danger_pl(pos['pos'])
                        pos['last_notify_perc'] = pl_perc

            # Sync state to datastore
            self.ds.pos_large_pl = pos_large_pl
            self.ds.pos_danger_pl = pos_danger_pl

            await asyncio.sleep(self.ex.config['position_check_interval'])



class TraderManager():

    def __init__(self,
                 mongo,
                 reset_state=False,
                 enable_api=False,
                 trader_args=None,
                 trader_kwargs=None,
                 apiserver_args=None,
                 apiserver_kwargs=None,
                 apiserver_run_args=None,
                 apiserver_run_kwargs=None):

        self.ds = Datastore.create("trader_manager")
        self.mongo = mongo
        self.apiserver = {}
        self.traders = {}
        self.futures = {}
        self.sigs = {}

        self.reset_state = reset_state
        self.enable_api = enable_api
        self.trader_args = trader_args
        self.trader_kwargs = trader_kwargs
        self.apiserver_args = apiserver_args
        self.apiserver_kwargs = apiserver_kwargs
        self.apiserver_run_args = apiserver_run_args
        self.apiserver_run_kwargs = apiserver_run_kwargs

    async def start(self, exs=[]):

        if self.enable_api:
            if not exs:
                raise ValueError(f"`exs` is required if api server is enabled")

            server = APIServer(self.mongo,
                               traders=self.traders,
                               trader_manager=self,
                               *self.apiserver_args,
                               **self.apiserver_kwargs)
            # Returns immediately
            await server.run(*self.apiserver_run_args, **self.apiserver_run_kwargs)

            if not isinstance(exs, list):
                exs = [exs]

            loop = asyncio.get_event_loop()
            sigs_futures = {}
            for ex in exs:
                self.sigs[ex] = Signals(self.mongo, ex, Indicator())
                sigs_futures[ex] = asyncio.run_coroutine_threadsafe(
                    self.sigs[ex].start(), loop)

        # Do not erase uid_ex on reset for now
        # if self.reset_state:
        #     self.ds.clear()

        while True:
            # ue == 'uid-ex', it's how it stored in redis

            uid_ex = self.ds.get('uid_ex', [])
            to_remove = []

            # Remove trader
            for ue in self.traders:
                if ue not in uid_ex and not self.traders[ue]._stop:
                    logger.info(f"Removing [{ue}]")
                    self.traders[ue].stop()

            # Add trader
            for ue in uid_ex:
                if ue not in self.traders:
                    logger.info(f"Adding [{ue}]")
                    self.start_trader(ue)
                    await asyncio.sleep(30)

            await asyncio.sleep(5)

            # Try to receive exception or result,
            # if a trader stopped normally, just remove it from the entry,
            # otherwise restart the trader.
            for ue in self.futures:
                try:
                    exp = self.futures[ue].exception(timeout=1)
                except concurrent.futures.TimeoutError:
                    pass
                else:
                    if self.traders[ue]._stop:
                        to_remove.append(ue)
                    else:
                        logger.warning(f"Trader [{ue}] got exception: {exp.__class__.__name__} {str(exp)}")
                        logger.info(f"Restaring trader [{ue}]")
                        self.start_trader(ue)

            for ue in to_remove:
                logger.debug(f'{ue} removed')
                del self.traders[ue]
                del self.futures[ue]

    def start_trader(self, ue, notify_start=True):
        uid, ex = ue.split('-')
        try:
            trader = SingleEXTrader(
                ex_id=ex,
                uid=uid,
                notify_start=notify_start ,
                *self.trader_args,
                **self.trader_kwargs)
        except KeyError:
            logger.warning(f"Trader [{ue}] has no exchange API key")
        else:
            loop = asyncio.get_event_loop()
            self.futures[ue] = asyncio.run_coroutine_threadsafe(
                async_catch_traceback(trader.start), loop)
            self.traders[ue] = trader

    async def restart_trader(self, uid, ex):
        """ Stop a trader and restart it. """
        ue = f"{uid}-{ex}"

        if not ue in self.traders:
            raise ValueError(f"{ue} is not active")

        logger.info(f"Restarting trader [{ue}] (on demand)")
        self.traders[ue].stop()
        await asyncio.sleep(5) # wait for trader to stop
        self.start_trader(ue, notify_start=False)
        await asyncio.sleep(10) # wait for trader to start
