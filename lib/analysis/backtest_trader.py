import copy
import logging
import pandas as pd
from copy import deepcopy
from datetime import timedelta
from pprint import pprint
from collections import OrderedDict

from utils import not_implemented,\
    config,\
    gen_id,\
    combine,\
    dt_ms,\
    ms_dt,\
    select_time,\
    roundup_dt,\
    dt_max,\
    Timer,\
    to_ordered_dict, \
    tf_td

# TODO: Use different configs (fee etc.) for different exchanges
# TODO: Add different order types

logger = logging.getLogger()


class SimulatedTrader():
    """ Available attributes:
            - trader: a Trader instance
            - markets: dict of list of symbols to trade,
                a subset of symbols in utils.currencies, eg. {
                    'bitfinex': ['BTC/USD', 'ETH/USD'],
                    'poloniex': ['BTC/USDT', ETH/USDT']
                }
            - timeframes: list of timeframes, eg. {
                'bitfinex': ['1m', '5m', ...]
            }
            - ohlcvs: dict of ohlcv DataFrames by symbol, eg. {
                'bitfinex': {
                    'BTC/USD': {
                        '1m': DataFrame(...),
                        '5m': DataFrame(...),
                    }
                }
            }
            - trades: dict of DataFrame of trades by symbol, eg. {
                'bitfinex': {
                    'BTC/USD': DataFrame(...),
                 }
            }
            - timer
        Available methods for strategy:
            - open
            - close_position
            - cancel_order
            - close_all_positions
            - cancel_all_orders
            - cur_price
        Available methods for backtesting:
            - feed_data
            - feed_ohlcv
            - feed_trade
            - tick
    """

    def __init__(self, timer, strategy=None, custom_config=None):
        # If custom_config is not specified, use default config
        _config = custom_config if custom_config else config
        self.config = _config['analysis']
        self._config = _config

        self.strategy = strategy
        self.timer = timer  # synchronization timer for backtesting
        self.markets = self.get_markets()
        self.timeframes = self.get_timeframes()
        self.fast_mode = False
        self._init()

    def _init(self):
        """ Initialize all trade-session-dependent variables. """
        self.timer.reset()
        self._init_account()

        self.ohlcvs = self.create_empty_ohlcv_store()
        self.trades = self.create_empty_trade_store()
        self.last_ohlcv = None
        self.last_trade = None

    def reset(self):
        self._init()

    def _init_account(self):
        funds = self.config['funds']
        self.wallet = self._init_wallet(funds)
        self.order_records = self._init_order_records()
        self.orders = self.order_records['orders']
        self.order_history = self.order_records['order_history']
        self.positions = self.order_records['positions']
        self.wallet_history = []
        self._order_count = 0

    def _init_order_records(self):
        ex_empty_dict = {ex: OrderedDict() for ex in self.markets}

        return {
            # active orders
            "orders": copy.deepcopy(ex_empty_dict),
            # inactive orders
            "order_history": copy.deepcopy(ex_empty_dict),
            # active margin positions
            "positions": copy.deepcopy(ex_empty_dict)
        }

    def _init_wallet(self, funds):
        def fundOf(ex, curr):
            return funds[ex][curr] if curr in funds[ex] else 0

        wallet = {}

        for ex in self.markets:
            wallet[ex] = {}
            for market in self.markets[ex]:
                curr1, curr2 = market.split('/')
                if curr1 not in wallet[ex]:
                    wallet[ex][curr1] = fundOf(ex, curr1)
                if curr2 not in wallet[ex]:
                    wallet[ex][curr2] = fundOf(ex, curr2)

        return wallet

    def create_empty_ohlcv_store(self):
        """ ohlcv[ex][market][ft] """
        cols = ['timestamp', 'open', 'close', 'high', 'low', 'volume']
        ohlcv = {}

        # Each exchange has different timeframes
        for ex, tfs in self.timeframes.items():
            dfs = {}

            for tf in tfs:
                dfs[tf] = pd.DataFrame(columns=cols)
                dfs[tf].set_index('timestamp', inplace=True)

            ohlcv[ex] = {}
            for market in self.markets[ex]:
                ohlcv[ex][market] = copy.deepcopy(dfs)

        return ohlcv

    def create_empty_trade_store(self):
        """ trades[ex][market] """
        cols = ['id', 'timestamp', 'side', 'price', 'amount']
        trades = {}

        df = pd.DataFrame(columns=cols)
        df.set_index('timestamp', inplace=True)

        for ex, markets in self.markets.items():
            trades[ex] = {}
            for market in markets:
                trades[ex][market] = copy.deepcopy(df)

        return trades

    def feed_ohlcv(self, ex_ohlcvs, end):
        """ Append new ohlcvs to data feed.
            Param
                ex_ohlcvs: contain 3 levels, exchange > symbol > timeframe
                {
                    'bitfinex': {                       # ex
                        'BTC/USD': {                    # tf
                            '1m': DataFrame(...),       # sym, ohlcv
                            '5m': DataFrame(...),
                        }
                    }
                }
        """
        last = self.last_ohlcv

        for ex, syms in ex_ohlcvs.items():
            for sym, tfs in syms.items():
                for tf, ohlcv in tfs.items():
                    if len(ohlcv) > 0:

                        tmp = ohlcv[:end]
                        self.ohlcvs[ex][sym][tf] = tmp

                        if len(tmp) > 0 \
                        and (last is None or tmp.index[-1] > last.name):
                            last = tmp.iloc[-1]

        if self.last_ohlcv is None or last.name > self.last_ohlcv.name:
            self.last_ohlcv = last
        else:
            last = None

        return last

    def feed_trade(self, ex_trades, end):
        """ Append new trades to data feed.
            Param
                ex_trades: contain 2 levels, exchange > symbol
                {
                    'bitfinex': {
                        'BTC/USD': DataFrame(...),
                        'ETH/USD': DataFrame(...),
                    }
                }
        """
        last = self.last_trade

        for ex, syms in ex_trades.items():
            for sym, trade in syms.items():
                if len(trade) > 0:

                    tmp = trade[:end]
                    self.trades[ex][sym] = tmp

                    if len(tmp) > 0 \
                    and (last is None or tmp.index[-1] > last.name):
                        last = tmp.iloc[-1]

        if self.last_trade is None or last.name > self.last_trade.name:
            self.last_trade = last
        else:
            last = None

        return last

    def feed_data(self, end, ex_ohlcvs=None, ex_trades=None):
        """ Param
                end: datetime, data feed time end for this test period
                ex_ohlcvs: same format as required in `feed_ohlcv`
                ex_trades: same format as required in `feed_trade`
        """
        # To significantly improve backtesting speed, do not provide trades data.

        last_ohlcv = None
        last_trade = None

        if ex_ohlcvs is not None and len(ex_ohlcvs) > 0:
            last_ohlcv = self.feed_ohlcv(ex_ohlcvs, end)

        if ex_trades is not None and len(ex_trades) > 0:
            last_trade = self.feed_trade(ex_trades, end)

        dt_ohlcv = last_ohlcv.name if last_ohlcv is not None else None
        dt_trade = last_trade.name if last_trade is not None else None
        max_dt = dt_max(dt_ohlcv, dt_trade)

        if max_dt is None:
            self.timer.tick()
        else:
            self.update_timer(self.timer, max_dt)

    @staticmethod
    def update_timer(timer, dt):
        dt = roundup_dt(dt, sec=timer.interval_sec())
        timer.set_now(dt)

    def tick(self, last=False):
        """ Execute pending orders. """
        if self._config['mode'] == 'debug':
            self._check_data_feed_time()

        self._execute_orders()

        if self.strategy is not None and not last:
            self.strategy.run()

    def _check_data_feed_time(self):
        """ Check whether data feed's time exceed timer's.
            Only work for SimulatedTrader, not FastTrader, because data is feed at once.
        """
        cur_time = self.timer.now()

        for ex, syms in self.ohlcvs.items():
            for market, tfs in syms.items():
                for tf, ohlcv in tfs.items():
                    if len(ohlcv) > 0 and ohlcv.index[-1] > cur_time:
                        raise ValueError(f"ohlcv feed's timestamp exceeds timer's :: {ohlcv.index[-1]} > {cur_time}")

        for ex, syms in self.trades.items():
            for market, trades in syms.items():
                if len(trades) > 0 and trades.index[-1] > cur_time:
                    raise ValueError(f"trade feed's timestamp exceeds timer's. :: {trades.index[-1]} > {cur_time}")

    @staticmethod
    def generate_order(ex, market, side, order_type, amount, price=None, *, margin=False, stop_loss=None, stop_profit=None):
        """ Helper function for generating order dict for `open`. """
        if order_type == 'limit' and not price:
            raise ValueError("limit orders must provide a price.")

        return {
            'ex': ex,
            'market': market,
            'side': side,
            'order_type': order_type,
            'amount': amount,
            'open_price': price,
            'margin': margin,
            'stop_loss': stop_loss,
            'stop_profit': stop_profit,
        }

    def open(self, order):
        """ Open an order to the market, will be executed on the next tick if price exceeds.
            Currently surpported order_type: limit, market
            Param
                order: {
                    'ex':
                    'market':
                    'side':
                    'order_type':
                    'amount':
                    'open_price': (if order_type is 'limit')
                }
        """
        if not self.is_valid_order(order):
            return None

        ex = order['ex']
        order = self._gen_order(order)
        if order['order_type'] == 'limit':
            if self.has_enough_balance(ex, order['currency'], order['cost']):
                self.wallet[ex][order['currency']] -= order['cost']
                self.orders[ex][order['#']] = order
                return order
            else:
                curr = order['currency']
                cost = order['cost']
                logger.warning(f"Not enough balance to open order => "
                            f"{curr}--{self.wallet[ex][curr]}<{cost}")
                return None
        else:
            # (order_type: market)
            # Assume the order will be fully executed anyway.
            # Balance will be substracted on order execution.
            self.orders[ex][order['#']] = order
            return order

    def _gen_order(self, order):
        curr = self.trading_currency(order=order)
        price = order['open_price'] if order['order_type'] == 'limit' else 0

        close_price = None
        if 'op_close_price' in order:
            close_price = order['op_close_price']

        order = {
            "#": self.order_count(),
            "uuid": gen_id(),
            "ex": order['ex'],
            "market": order['market'],
            "side": order['side'],
            "order_type": order['order_type'],
            "open_time": self.timer.now(),
            "close_time": None,    # filled after closed/canceled/executed
            "open_price": price,        # open price
            "amount": order['amount'],
            "currency": curr,
            "cost": 0,                  # filled before open
            "fee": 0,                   # filled before open
            "canceled": False,          # filled after canceled
            "margin": order['margin'],
            "op_close_price": close_price
        }
        margin_order = {
            "active": False,
            "margin_fee": 0,            # filled before open if "margin" is True
            "margin_fund": 0,           # filled before open if "margin" is True
            "close_price": 0,           # filled after closed
            "PL": 0,                    # filled after closed
        }

        if order['margin']:
            order = combine(order, margin_order)

        if order['order_type'] == 'limit':
            self._calc_order(order)

        return order

    @staticmethod
    def is_valid_order(order):
        """ Check fields in the order. """
        order_fields = ['market', 'side', 'order_type', 'amount']

        if order['order_type'] == 'limit':
            order_fields += ['open_price']

        if not set(order_fields).issubset(order.keys()):
            logger.warning(f"Invalid order {order}")
            return False

        if order['order_type'] == 'limit' and order['open_price'] == 0:
            logger.warning(f"Cannot open order at price 0")
            return False

        return True

    def close_position(self, order):
        id = order['#']
        ex = order['ex']

        if id in self.positions[ex]:
            order = self.positions[ex][id]

            # queue the order again for trader to close
            if id not in self.orders[ex]:
                self.orders[ex][id] = order
            return order
        else:
            return None

    def cancel_order(self, order):
        id = order['#']
        ex = order['ex']

        if id in self.orders[ex]:
            order['canceled'] = True
            order['close_time'] = self.timer.now()

            self.wallet[ex][order['currency']] += order['cost']
            self.order_history[ex][id] = order
            del self.orders[ex][id]
            return order
        else:
            return None

    def close_all_positions(self, ex, side='all'):
        """
            Param
                ex: str, which ex's positions to close
                side: 'buy'/'sell' (optional), which side of positions to close
        """
        del_orders = []
        positions = deepcopy(self.positions[ex])

        for id, order in positions.items():
            if (side == 'all')\
            or (order['side'] == side):
                if self.close_position(order):
                    del_orders.append(order)

        return del_orders

    def cancel_all_orders(self, ex, side='all'):
        """ NOTE: Need to be called before `close_all_positions` or margin orders
                  queued to self.orders will be canceled.

            Param
                ex: str, which ex's orders to cancel
                side: 'buy'/'sell' (optional), which side of orders to cancel
        """
        del_orders = []
        orders = deepcopy(self.orders[ex])

        for id, order in orders.items():
            if self.is_margin_close(order):
                continue # skip if the order is queued to close

            if (side == 'all')\
            or (order['side'] == side):
                if self.cancel_order(order):
                    del_orders.append(order)

        return del_orders

    def _execute_orders(self):
        """ Execute orders in queue.
            If order_type is 'limit', it will check if current price exceeds the target.
            If order_type is 'market', it will execute at current price if balance is enough.
        """
        def execute_open_position(order):
            order['active'] = True
            del self.orders[ex][order['#']]
            self.positions[ex][order['#']] = order

        def execute_close_position(order):
            ex = order['ex']

            if order['op_close_price']:
                order['close_price'] = order['op_close_price']
            else:
                order['close_price'] = self.cur_price(ex, order['market'])

            order['close_time'] = self.timer.now()
            order['active'] = False

            self._calc_order(order)
            earn = self._calc_margin_return(order)

            self.wallet[ex][order['currency']] += earn
            self.order_history[ex][order['#']] = order
            self.wallet_history.append(self.wallet[ex][order['currency']])

            del self.positions[ex][order['#']]
            del self.orders[ex][order['#']]

        def execute_normal_order(order):
            order['close_time'] = self.timer.now()
            curr = order['currency']
            opp_curr = self.opposite_currency(order, curr)

            if self.is_buy(order):
                self.wallet[ex][opp_curr] += order['amount']
            else:
                self.wallet[ex][opp_curr] += order['amount'] * order['open_price']

            del self.orders[ex][order['#']]
            self.order_history[ex][order['#']] = order

        copy_orders = deepcopy(self.orders)
        for ex, orders in copy_orders.items():
            for id, order in orders.items():

                # print(self.wallet['bitfinex']['USD'])

                # Close margin position, all margin orders are closed at market price
                if self.is_margin_close(order):
                    execute_close_position(order)

                # Execute limit order
                elif order['order_type'] == 'limit':

                    if self._match_order(order):
                        if order['margin']:
                            execute_open_position(order)
                        else:
                            execute_normal_order(order)

                # Execute market order
                elif order['order_type'] == 'market':

                    order['open_price'] = self.cur_price(ex, order['market'])
                    self._calc_order(order)

                    if order['margin']:

                        if self.has_enough_balance(ex, order['currency'], order['cost']):
                            self.wallet[ex][order['currency']] -= order['cost']
                            execute_open_position(order)
                        else:
                            logger.warning(f"Not enough balance to open margin position: {order}")
                            self.wallet[ex][order['currency']] -= order['cost'] # will be restored on cancellation
                            self.cancel_order(order)

                    else:  # normal order

                        if self.has_enough_balance(ex, order['currency'], order['cost']):
                            self.wallet[ex][order['currency']] -= order['cost']
                            execute_normal_order(order)
                        else:
                            logger.warning(f"Not enough balance to execute normal market order: {order}")
                            self.wallet[ex][order['currency']] -= order['cost'] # will be restored on cancellation
                            self.cancel_order(order)

    def has_enough_balance(self, ex, curr, cost):
        if self.wallet[ex][curr] < cost:
            ## TODO: fix margin trading cost > balance by little
            return False
        else:
            return True

    @staticmethod
    def trading_currency(market=None, side=None, margin=None, order=None):
        """ Return the cost currency. """
        if order:
            market = order['market']
            side = order['side']
            margin = order['margin']
        elif market is None or side is None or margin is None:
            raise ValueError(f"Miss at least one parameter.")

        curr = ''
        if margin:
            curr = market.split('/')[1]  # qoute balance
        elif side == 'buy':
            curr = market.split('/')[1]  # qoute balance
        elif side == 'sell':
            curr = market.split('/')[0]  # base balance
        else:
            raise ValueError("Invalid parameters in `trading_currency`")
        return curr

    @staticmethod
    def quote_balance(market):
        return market.split('/')[1]

    @staticmethod
    def base_balance(market):
        return market.split('/')[0]

    def _match_order(self, order):
        cond1 = (self.cur_price(order['ex'], order['market']) == order['open_price'])
        cond2 = (self.cur_price(order['ex'], order['market']) < order['open_price'])

        if (cond1)\
        or (self.is_buy(order) and cond2)\
        or (self.is_sell(order) and not cond2):
            return True
        else:
            return False

    def get_markets(self):
        markets = {}
        for ex, info in self.config['exchanges'].items():
            markets[ex] = info['markets']
        return markets

    def get_timeframes(self):
        tfs = {}
        for ex, info in self.config['exchanges'].items():
            tfs[ex] = info['timeframes']
        return tfs

    @staticmethod
    def opposite_currency(order, curr):
        currs = order['market'].split('/')
        currs.remove(curr)
        return currs[0]

    def cur_price(self, ex, market):
        if self.fast_mode:
            raise RuntimeError('SimulatedTrader cur_price is called in fast mode.')

        # last_ohlcv = self.get_last_ohlcv(ex, market)
        last_ohlcv = self.ohlcvs[ex][market][self.config['indicator_tf']].iloc[-1]
        return last_ohlcv.close

    def order_count(self):
        self._order_count += 1
        return self._order_count

    def is_position_open(self, order):
        if not isinstance(order, dict) or '#' not in order or 'ex' not in order:
            return False
        return True if order['#'] in self.positions[order['ex']] else False

    def _calc_order(self, order):

        if not order['margin']:
            if self.is_buy(order):
                order['cost'] = order['open_price'] * order['amount']
                order['amount'] = order['cost'] * (1 - self.config['fee']) / order['open_price']
                order['fee'] = order['open_price'] * order['amount'] * self.config['fee']
            else:
                order['cost'] = order['amount']
                order['fee'] = order['amount'] * (1 - self.config['fee'])
        else:
            # opening a margin position
            if not self.is_position_open(order):
                P = order['open_price']
                F = self.config['fee']
                MF = self.config['margin_fee']
                MR = self.config['margin_rate']
                mf = MF / (MR - 1) if MR > 1 else 0

                order['cost'] = order['amount'] / MR * P
                order['amount'] = order['cost'] / (1 / MR + F + mf) / P
                order['margin_fund'] = order['amount'] / MR * (MR - 1) * P
                order['margin_fee'] = order['margin_fund'] * MF
                order['fee'] = P * order['amount'] * F

            else:  # closing a margin position
                order['fee'] += order['amount'] * order['close_price'] * self.config['fee']
                order['PL'] = self._calc_margin_pl(order)

    def _calc_margin_pl(self, order):
        price_diff = order['close_price'] - order['open_price']

        if order['side'] == 'sell':
            price_diff *= -1

        pl = price_diff * order['amount'] - order['fee'] - order['margin_fee']
        return pl

    def _calc_margin_return(self, order):
        price_diff = order['close_price'] - order['open_price']

        if order['side'] == 'sell':
            price_diff *= -1

        close_fee = order['close_price'] * order['amount'] * self.config['fee']
        result = order['open_price'] * order['amount'] / self.config['margin_rate'] \
               + price_diff * order['amount'] - close_fee

        return result

    def get_hist_margin_orders(self, ex, market):
        margin_orders = []

        for order in self.order_history[ex].values():
            if order['margin'] and order['market'] == market:
                margin_orders.append(order)

        return margin_orders

    def get_hist_normal_orders(self, ex, market):
        normal_orders = []

        for order in self.order_history[ex].values():
            if not order['margin'] and order['market'] == market:
                normal_orders.append(order)

        return normal_orders

    def liquidate(self):
        for ex, markets in self.markets.items():
            self.cancel_all_orders(ex)
            self.close_all_positions(ex)

        self.tick(last=True)  # force execution of all close position orders

    def get_last_ohlcv(self, ex, market, now=None):
        """ Find latest ohlcv from all timeframes. """
        last = self.ohlcvs[ex][market]['1m'].iloc[0]

        for tf, ohlcv in self.ohlcvs[ex][market].items():
            if now is None: # slow mode
                if len(ohlcv) > 0:
                    tmp = ohlcv.iloc[-1]
            else: # fast mode
                if len(ohlcv) > 0:
                    tmp = ohlcv[:now].iloc[-1]

            if tmp.name > last.name:
                last = tmp

        return last

    def latest_ohlcv_timeframe(self, ex, market, now):
        """ Return the timeframe having latest datetime. """
        latest_tf = ''
        latest_dt = self.ohlcvs[ex][market]['1m'].iloc[0].name
        for tf, ohlcv in self.ohlcvs[ex][market].items():
            tmp = ohlcv[:now].iloc[-1]
            if tmp.name > latest_dt:
                latest_dt = tmp.name
                latest_tf = tf

        return latest_tf

    @classmethod
    def is_margin_open(cls, order):
        return not cls.is_margin_close(order)

    @classmethod
    def is_margin_close(cls, order):
        if (order['margin'] and order['active'])\
        or (order['margin'] and order['close_time']):
            return True
        else:
            return False

    @staticmethod
    def is_buy(order):
        return True if order['side'] == 'buy' else False

    @staticmethod
    def is_sell(order):
        return True if order['side'] == 'sell' else False

    @staticmethod
    def is_up_bar(bar):
        return (bar.close > bar.open)


class FastTrader(SimulatedTrader):

    def __init__(self, timer, strategy=None, custom_config=None):
        super().__init__(timer, strategy, custom_config)
        self._init()

    def _init(self):
        super()._init()
        self.op_init_account()

    def op_init_account(self):
        funds = self.config['funds']
        self.op_wallet = self._init_wallet(funds)
        self.op_order_records = self._init_order_records()
        self.op_orders = self.op_order_records['orders']
        self.op_positions = self.op_order_records['positions']
        self._op_order_count = 0

    def reset(self):
        super().reset()
        self._init()

    def tick(self, last=False):
        if last: # spcial case, forcing order execution after time ends
            super().tick(last)
            return

        end = self.timer.now()
        self.timer.reset()

        ops = self.strategy.fast_run()
        self.ops = ops

        if len(ops) == 0:
            self.update_timer(self.timer, end)
            return

        real_orders = {}
        self.timer.reset()
        cur_time = self.timer.now()

        # print('---------------------------')

        while cur_time < end:

            self._execute_orders()

            executed_ops = []
            for op in ops:
                dt = op['time']
                if op and dt <= cur_time:
                    if op['name'] == 'open_order':
                        real_orders[op['order']['op_#']] = self.open(op['order'])

                    elif op['name'] == 'close_position':
                        order = real_orders[op['order']['op_#']]
                        self.close_position(order)

                    elif op['name'] == 'cancel_order':
                        order = real_orders[op['order']['op_#']]
                        self.cancel_order(order)

                    elif op['name'] == 'close_all_positions':
                        self.close_all_positions(op['ex'], op['side'])

                    elif op['name'] == 'cancel_all_orders':
                        self.cancel_all_orders(op['ex'], op['side'])

                    else:
                        raise ValueError(f"op name is invalid: {op['name']}")

                    executed_ops.append(op)
                else:
                    break

            # remove executed ops
            for op in executed_ops:
                ops.remove(op)

            if self.has_open_orders():
                # Move current time by one interval to execute pending orders on next round
                self.timer.tick()
            elif len(ops) > 0:
                # No active order is waiting for execution, skip to next op.
                dt = ops[0]['time']
                self.update_timer(self.timer, dt)
            else:
                # No ops in queue, skip to the end
                self.update_timer(self.timer, end)

            cur_time = self.timer.now()

    def has_open_orders(self):
        for ex, orders in self.orders.items():
            if len(orders) > 0:
                return True
        return False

    def cur_price(self, ex, market, now=None):
        if not self.fast_mode:
            raise RuntimeError('FastTrader cur_price is called in non-fast mode.')

        if now is None:
            now = self.timer.now()

        last_ohlcv = self.ohlcvs[ex][market][self.config['indicator_tf']][:now].iloc[-1]
        return last_ohlcv.close

    def op_open(self, order, now):
        order['op_#'] = self.op_order_count()
        op = {
            'name': 'open_order',
            'time': now,
            'order': order
        }
        self.op_execute(op)
        return op

    def op_close_position(self, order, now):
        if not order['margin']:
            raise ValueError(f"A normal order can't be closed.")

        if 'op_close_price' in order:
            real_order = self.op_positions[order['ex']][order['op_#']]
            real_order['op_close_time'] = order['op_close_time']
            real_order['op_close_price'] = order['op_close_price']
            order = real_order

        op = {
            'name': 'close_position',
            'time': now,
            'order': order
        }
        self.op_execute(op)
        return op

    def op_cancel_order(self, order, now):
        op = {
            'name': 'cancel_order',
            'time': now,
            'order': order
        }
        self.op_execute(op)
        return op

    def op_close_all_positions(self, ex, now, side='all'):
        op = {
            'name': 'close_all_positions',
            'time': now,
            'ex': ex,
            'side': side
        }
        self.op_execute(op)
        return op

    def op_cancel_all_orders(self, ex, now, side='all'):
        op = {
            'name': 'cancel_all_orders',
            'time': now,
            'ex': ex,
            'side': side
        }
        self.op_execute(op)
        return op

    def op_order_count(self):
        self._op_order_count += 1
        return self._op_order_count

    def op_execute(self, op):
        """ Roughly calculate balance and maintain op_wallet. """
        now = op['time']

        # Execute previous limit orders
        executed = []
        for ex, orders in self.op_orders.items():
            for _, order in orders:
                if self.op_match_limit_order(order, now):
                    self.op_execute_open_order(order, order['op_open_price'])
                    executed.append(order)

        # Delete executed orders
        for order in executed:
            del self.op_orders[order['op_#']]

        # Execute open_order
        if op['name'] == 'open_order':
            order = op['order']
            order['op_open_time'] = now

            if order['order_type'] == 'limit':
                # If order type is limit, just put the order in the queue.
                # It'll be executed when op_execute is called.
                # Question: Should balance be preserved (substracted) before execution?
                self.op_orders[order['op_#']] = order

            else:  # order type: market
                # Execute market orders immediately
                price = self.cur_price(order['ex'], order['market'], now)
                self.op_execute_open_order(order, price)

        elif op['name'] == 'close_position':
            order = op['order']
            curr = self.trading_currency(order=order)

            if order['op_#'] in self.op_positions[order['ex']]:
                if 'op_close_price' in order:
                    price = order['op_close_price']
                else:
                    price = self.cur_price(order['ex'], order['market'], now)

                _, earn = self.op_calc_cost_earn(order, price)

                self.op_wallet[order['ex']][curr] += earn
                del self.op_positions[order['ex']][order['op_#']]
            else:
                logger.debug(f"{order['op_#']} is not in op_positions")

        elif op['name'] == 'cancel_order':
            # Only limit order can be canceled
            # Balance is not preserved at open, so no need to restore balance.
            order = op['order']
            if order['order_type'] == 'limit' and order['op_#'] in self.op_orders:
                del self.op_orders[order['op_#']]

        elif op['name'] == 'close_all_positions':
            positions = deepcopy(self.op_positions[op['ex']])
            for id, order in positions.items():
                if op['side'] == 'all' or order['side'] == op['side']:
                    self.op_close_position(order, now)

        elif op['name'] == 'cancel_all_orders':
            orders = deepcopy(self.op_orders[op['ex']])
            for id, order in orders.items():
                if op['side'] == 'all' or order['side'] == op['side']:
                    self.op_cancel_order(order, now)

    def op_execute_open_order(self, order, price):
        cost, earn = self.op_calc_cost_earn(order, price)
        curr = self.trading_currency(order=order)
        opp_curr = self.opposite_currency(order, curr)

        # Check if have enough balance
        if self.op_wallet[order['ex']][curr] >= cost:
            self.op_wallet[order['ex']][curr] -= cost

            if not order['margin']:
                self.op_wallet[order['ex']][opp_curr] += earn
            else:
                self.op_positions[order['ex']][order['op_#']] = order

            return True
        else:
            logger.debug('Not enough balance')
            return False

    def op_calc_cost_earn(self, order, price):
        if order['market'] and not price:
            raise ValueError("Missing `price` paramter")

        cost = 0
        earn = 0
        amount = order['amount']

        # print(self.op_wallet['bitfinex']['USD'])

        if not order['margin']:
            if self.is_buy(order):
                cost = price * amount
                earn = amount * (1 - self.config['fee'])
            else:  # sell
                cost = amount
                earn = amount * (1 - self.config['fee']) * price

        else:
            # opening a margin position, earn = 0
            if not order['op_#'] in self.op_positions[order['ex']]:
                P = price
                F = self.config['fee']
                MF = self.config['margin_fee']
                MR = self.config['margin_rate']
                mf = MF / (MR - 1) if MR > 1 else 0

                order['op_open_price'] = price

                cost = amount / MR * P
                order['op_amount'] = cost / (1 / MR + F + mf) / P

            else: # closing a margin position, cost = 0
                amount = order['op_amount']
                price_diff = price - order['op_open_price']
                close_fee = price * amount * self.config['fee']

                if order['side'] == 'sell':
                    price_diff *= -1

                earn = order['op_open_price'] * amount / self.config['margin_rate'] \
                       + price_diff * amount - close_fee

        return cost, earn

    def op_match_limit_order(self, order, now):
        ex = order['ex']
        market = order['market']
        tf = self.latest_ohlcv_timeframe(ex, market, now)

        # Get the ohlcv between open time and now
        ohlcv = self.ohlcvs[ex][market][tf][order['op_open_time']:now]

        if self.is_buy(order) and (ohlcv.close <= order['open_price']).any():
            return True
        elif self.is_sell(order) and (ohlcv.close >= order['open_price']).any():
            return True

        return False