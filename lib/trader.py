import copy
import logging
import pandas as pd
from datetime import timedelta
from pdb import set_trace as trace
from pprint import pprint

from utils import not_implemented,\
    config,\
    gen_id,\
    combine,\
    dt_ms,\
    ms_dt,\
    select_time,\
    roundup_dt,\
    pdts_dt,\
    dt_max,\
    Timer,\
    to_ordered_dict

# TODO: Use different config (fee etc.) for different exchanges
# TODO: Add different order type

logger = logging.getLogger()
_config = config


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
        if custom_config:
            self.config = custom_config['trader']
            _config = custom_config  # change global config to custom_config
        else:
            self.config = config['trader']

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

    def _init_account(self, funds=None):
        ex_empty_dict = {ex: {} for ex in self.markets}

        if not funds:
            funds = self.config['funds']

        self.order_records = {
            # active orders
            "orders": copy.deepcopy(ex_empty_dict),
            # inactive orders
            "order_history": copy.deepcopy(ex_empty_dict),
            # active margin positions
            "positions": copy.deepcopy(ex_empty_dict)
        }

        self.wallet = self._init_wallet(funds)
        self.orders = self.order_records['orders']
        self.order_history = self.order_records['order_history']
        self.positions = self.order_records['positions']
        self._order_count = 0

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

                        if last is None or tmp.index[-1] > last.name:
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

                    if last is None or tmp.index[-1] > last.name:
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

        if ex_ohlcvs is not None:
            last_ohlcv = self.feed_ohlcv(ex_ohlcvs, end)

        if ex_trades is not None:
            last_trade = self.feed_trade(ex_trades, end)

        dt_ohlcv = last_ohlcv.name if last_ohlcv is not None else None
        dt_trade = last_trade.name if last_trade is not None else None
        max_dt = dt_max(dt_ohlcv, dt_trade)

        self.update_timer(max_dt)

        if _config['mode'] == 'debug':
            self._debug_feed_data()

    def _debug_feed_data(self):

        ### For checking if data is correct ###
        ### If errors are raised means ohlcv and trade timestamp doesn't match. ###
        # if max_dt is not None:
        #     dt_ohlcv = '' if dt_ohlcv is None else dt_ohlcv
        #     dt_trade = '' if dt_trade is None else dt_trade
        #     logger.debug(f"last ohlcv/trade feeded "
        #                  f"{dt_ohlcv.__str__():<19} || "
        #                  f"{dt_trade.__str__():<19}")

        dt_diff = timedelta(seconds=60)

        if self.last_ohlcv is not None and self.last_trade is not None:
            if self.last_trade.name - self.last_ohlcv.name > dt_diff:
                raise ValueError(f"trade timestamp {self.last_trade.name} > "
                                 f"ohlcv timestamp {self.last_ohlcv.name} by more than 1 minute")

    def update_timer(self, dt):
        if dt is None:
            self.timer.tick()
        else:
            dt = roundup_dt(dt, sec=self.timer.interval_sec())
            self.timer.set_now(dt)

    def tick(self, last=False):
        """ Execute pending orders. """
        if _config['mode'] == 'debug':
            self._check_data_feed_time()

        self._execute_orders()

        if self.strategy is not None and not last:
            self.strategy.run()

    def _check_data_feed_time(self):
        cur_time = self.timer.now()

        for ex, syms in self.ohlcvs.items():
            for market, tfs in syms.items():
                for tf, ohlcv in tfs.items():
                    if len(ohlcv) > 0 and ohlcv.index[-1] > cur_time:
                        raise ValueError(f"ohlcv feed's timestamp exceeds timer's :: {ohlcv.index[-1]} > {cur_time}")

        for ex, syms in self.trades.items():
            for market, trades in syms.items():
                if len(trades) > 0 and trades.index[-1] > cur_time:
                    raise ValueError(f"trades feed's timestamp exceeds timer's. :: {trades.index[-1]} > {cur_time}")

    @staticmethod
    def generate_order(ex, market, side, order_type, amount, price=None, *, margin=False):
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
            'margin': margin
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
                logger.warn(f"Not enough balance to open order => "
                            f"{curr}--{self.wallet[ex][curr]}<{cost}")
                return None
        else:
            # (order_type: market)
            # Assume the order will be fully executed anyway.
            # Balance will be substracted on order execution.
            self.orders[ex][order['#']] = order
            return order

    def _gen_order(self, order):
        curr = self.trading_currency(order['market'], order['side'], order['margin'])
        price = order['open_price'] if order['order_type'] == 'limit' else 0
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
            if not order['margin']:
                self._calc_order(order)
            else:
                self._calc_margin_order(order)

        return order

    @staticmethod
    def is_valid_order(order):
        """ Check fields in the order. """
        order_fields = ['market', 'side', 'order_type', 'amount']

        if order['order_type'] == 'limit':
            order_fields += ['open_price']

        if not set(order_fields).issubset(order.keys()):
            logger.warn(f"Invalid order {order}")
            return False

        if order['order_type'] == 'limit' and order['open_price'] == 0:
            logger.warn(f"Cannot open order at price 0")
            return False

        return True

    def close_position(self, order):
        id = order['#']
        ex = order['ex']

        if id in self.positions[ex]:
            order = self.positions[ex][id]

            # queue the order to activate order again for trader to execute
            self.orders[ex][id] = order
            return order
        else:
            return None

    def cancel_order(self, order):
        id = order['#']
        ex = order['ex']

        if id in self.orders[ex]:
            order = self.orders[ex][id]
            order['canceled'] = True
            order['close_time'] = self.timer.now()

            self.wallet[ex][order['currency']] += order['cost']
            self.order_history[ex][id] = order
            del self.orders[ex][id]
            return order
        else:
            return None

    def close_all_positions(self, ex):
        orders = []
        for id, order in self.positions[ex].items():
            if self.close_position(order):
                orders.append(order)
        return orders

    def cancel_all_orders(self, ex):
        orders = []
        for id, order in self.orders[ex].items():
            if self.cancel_order(order):
                orders.append(order)
        return orders

    def _execute_orders(self):
        """ Execute orders in queue.
            If order_type is 'limit', it will check if current price exceeds the target.
            If order_type is 'market', it will execute at current price if balance is enough.
        """
        executed_orders = []

        def execute_open_position(order):
            order['active'] = True
            self.positions[ex][order['#']] = order
            executed_orders.append(order)

        def execute_close_position(order):
            ex = order['ex']
            order['close_price'] = self.cur_price(ex, order['market'])
            order['close_time'] = self.timer.now()
            order['active'] = False
            self._calc_margin_order(order)
            self.wallet[ex][order['currency']] += self._calc_margin_return(order)
            del self.positions[ex][order['#']]
            executed_orders.append(order)

        def execute_normal_order(order):
            order['close_time'] = self.timer.now()
            curr = self.opposite_currency(order)

            if self.is_buy(order):
                self.wallet[ex][curr] += order['amount']
            else:
                self.wallet[ex][curr] += order['amount'] * order['open_price']
            executed_orders.append(order)

        for ex, orders in self.orders.items():
            for id, order in orders.items():

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

                    if order['margin']:
                        self._calc_margin_order(order)

                        if self.has_enough_balance(ex, order['currency'], order['cost']):
                            self.wallet[ex][order['currency']] -= order['cost']
                            execute_open_position(order)
                        else:
                            logger.warn(f"Not enough balance to open margin position: {order}")
                            self.cancel_order(order)

                    else:  # normal order
                        self._calc_order(order)

                        if self.has_enough_balance(ex, order['currency'], order['cost']):
                            self.wallet[ex][order['currency']] -= order['cost']
                            execute_normal_order(order)
                        else:
                            logger.warn(f"Not enough balance to execute normal market order: {order}")
                            self.cancel_order(order)

        for order in executed_orders:
            del self.orders[ex][order['#']]
            if not (order['margin'] and order['active']):  # if not an opened position order
                self.order_history[ex][order['#']] = order

    def has_enough_balance(self, ex, curr, cost):
        if self.wallet[ex][curr] < cost:
            return False
        else:
            return True

    @staticmethod
    def trading_currency(market, side, margin):
        curr = ''
        if margin:
            curr = market.split('/')[1]
        elif side == 'buy':
            curr = market.split('/')[1]  # qoute balance
        elif side == 'sell':
            curr = market.split('/')[0]  # base balance
        else:
            raise ValueError("Invalid parameters in `trading_currency`")
        return curr

    def _match_order(self, order):
        cond1 = (self.cur_price(order['ex'], order[
                 'market']) == order['open_price'])
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
    def opposite_currency(order):
        currs = order['market'].split('/')
        currs.remove(order['currency'])
        return currs[0]

    def cur_price(self, ex, market):
        if self.fast_mode:
            raise RuntimeError('SimulatedTrader cur_price is called in fast mode.')

        if len(self.trades[ex][market]) > 0:
            return self.trades[ex][market].iloc[-1]['price']
        else:
            return self.ohlcvs[ex][market]['1m'].iloc[-1]['close']

    def order_count(self):
        self._order_count += 1
        return self._order_count

    def is_position_open(self, order):
        if not isinstance(order, dict) or '#' not in order or 'ex' not in order:
            return False
        return True if order['#'] in self.positions[order['ex']] else False

    def _calc_order(self, order):

        if self.is_buy(order):
            order['cost'] = order['open_price'] * order['amount']
            order['fee'] = order['open_price'] * \
                order['amount'] * self.config['fee']
            remain = order['cost'] - order['fee']
            order['amount'] = remain / order['open_price']
        else:
            order['cost'] = order['amount']
            order['fee'] = order['amount'] * self.config['fee']
            order['amount'] -= order['fee']

    def _calc_margin_order(self, order):
        if not order['active']:  # opening a margin position
            base_amount = order['amount'] / self.config['margin_rate']
            order['margin_fund'] = order['amount'] - base_amount
            order['margin_fee'] = order['margin_fund'] * self.config['margin_fee']
            order['fee'] += order['open_price'] * \
                order['amount'] * self.config['fee']
            order['cost'] = order['open_price'] * base_amount + \
                order['fee'] + order['margin_fee']
        else:  # closing a margin position
            order['fee'] += order['open_price'] * \
                order['amount'] * self.config['fee']
            order['PL'] = self._calc_margin_pl(order)

    def _calc_margin_pl(self, order):
        price_diff = order['close_price'] - order['open_price']

        if order['side'] == 'sell':
            price_diff *= -1

        pl = price_diff * order['amount'] - order['fee'] - order['margin_fee']
        return pl

    def _calc_margin_return(self, order):
        base_amount = order['amount'] / self.config['margin_rate']
        PL = self._calc_margin_pl(order)
        return order['open_price'] * base_amount + PL

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



class FastTrader(SimulatedTrader):

    def __init__(self, timer, strategy=None, custom_config=None):
        super().__init__(timer, strategy, custom_config)
        self._init()

    def _init(self):
        super()._init()
        self._op_order_count = 0

    def reset(self):
        super().reset()
        self._init()

    def tick(self, last=False):
        if last:
            super().tick(last)
            return

        if _config['mode'] == 'debug':
            self._check_data_feed_time()

        fast_mode_timer = Timer(self.timer.start, self.timer.interval)

        ops = self.strategy.fast_run()
        ops = to_ordered_dict(ops, sort_by='key')

        if len(ops) == 0:
            return

        real_orders = {}
        cur_time = fast_mode_timer.now()
        end = self.timer.now()

        while cur_time < end:

            executed_ops_dt = []
            for dt, op in ops.items():

                if dt <= cur_time:
                    if op['name'] == 'open':
                        real_orders[op['order']['op_#']] = self.open(op['order'])

                    elif op['name'] == 'close_position':
                        order = real_orders[op['order']['op_#']]
                        self.close_position(order)

                    elif op['name'] == 'cancel_order':
                        order = real_orders[op['order']['op_#']]
                        self.cancel_order(order)

                    elif op['name'] == 'close_all_positions':
                        self.close_all_positions(op['ex'])

                    elif op['name'] == 'cancel_all_orders':
                        self.cancel_all_orders(op['ex'])

                    executed_ops_dt.append(dt)
                else:
                    break

            # remove executed ops
            for dt in executed_ops_dt:
                del ops[dt]

            if self.has_open_orders():
                fast_mode_timer.tick()
            else:
                # No active order is waiting for execution, skip to next op.
                dt = ops.items()[0][0]
                fast_mode_timer.set_now(dt)

            cur_time = fast_mode_timer.now()

    def has_open_orders(self):
        for ex, orders in self.orders.items():
            if len(orders) > 0:
                return True
        return False

    def cur_price(self, ex, market):
        now = self.timer.now()
        if len(self.trades[ex][market]) > 0:
            return self.trades[ex][market][:now].iloc[-1]['price']
        else:
            return self.ohlcvs[ex][market]['1m'][:now].iloc[-1]['close']

    def op_open(self, order):
        order['op_#'] = self.op_order_count()
        op = {
            'name': 'open',
            'order': order
        }
        return op

    def op_close_position(self, order):
        if not order['margin']:
            raise ValueError(f"A normal order can't be closed.")
        op = {
            'name': 'close_position',
            'order': order
        }
        return op

    def op_cancel_order(self, order):
        op = {
            'name': 'cancel_order',
            'order': order
        }
        return op

    def op_close_all_positions(self, ex):
        op = {
            'name': 'close_all_positions',
            'ex': ex
        }
        return op

    def op_cancel_all_orders(self, ex):
        op = {
            'name': 'cancel_all_orders',
            'ex': ex
        }
        return op

    def op_order_count(self):
        self._op_order_count += 1
        return self._op_order_count

