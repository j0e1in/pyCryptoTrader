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
    dt_max

# TODO: Use different config (fee etc.) for different exchanges
# TODO: Add different order type

logger = logging.getLogger()


class SimulatedTrader():
    """ Available attributes:
            - trader: a Trader instance
            - markets: dict of list of symbols to trade,
                a subset of symbols in utils.currencies, eg. {
                    'bitfinex': ['BTC/USD', 'ETH/USD'],
                    'poloniex': ['BTC/USDT', ETH/USDT']
                }
            - timeframes: list of timeframes, eg. ['1m', '5m', ...]
            - ohlcvs: dict of ohlcv DataFrames by symbol, eg. {
                'BTC/USD': {
                    '1m': DataFrame(...),
                    '5m': DataFrame(...),
                }
            }
            - trades: dict of DataFrame of trades by symbol, eg. {
                'BTC/USD': DataFrame(...),
                ...
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
            - feed_ohlcv
            - feed_trades
    """

    def __init__(self, timer):
        self.config = config['trader']
        self.timer = timer  # synchronization timer for backtesting

        self.markets = self.get_markets()
        self.timeframes = self.get_timeframes()

        self.account = None
        self.init_account()

        self.ohlcvs = self.create_empty_ohlcv_store()
        self.trades = self.create_empty_trade_store()
        self.last_ohlcv = None
        self.last_trade = None

    def init_account(self, funds=None):
        ex_empty_dict = {ex: {} for ex in self.markets}

        if not funds:
            funds = self.config['funds']

        self.account = {
            "wallet": self._init_wallet(funds),
            "orders": copy.deepcopy(ex_empty_dict),                 # active orders
            "order_history": copy.deepcopy(ex_empty_dict),          # inactive orders
            "positions": copy.deepcopy(ex_empty_dict)               # active margin positions
        }

        self.wallet = self.account['wallet']
        self.orders = self.account['orders']
        self.order_history = self.account['order_history']
        self.positions = self.account['positions']
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
        """ ohlcv[ex][tf][market] """
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

    def feed_ohlcv(self, ex_ohlcv):
        """ Append new ohlcvs to data feed.
            Param
                ex_ohlcv: contain 3 levels, exchange > symbol > timeframe
                {
                    'bitfinex': {                       # ex
                        'BTC/USD': {                    # tf
                            '1m': DataFrame(...),       # sym, ohlcv
                            '5m': DataFrame(...),
                        }
                    }
                }
        """
        last = None

        for ex, syms in ex_ohlcv.items():
            for sym, tfs in syms.items():
                for tf, ohlcv in tfs.items():
                    if len(ohlcv) > 0:
                        self.ohlcvs[ex][sym][tf] = \
                            self.ohlcvs[ex][sym][tf].append(ohlcv)

                        if not last or ohlcv.iloc[-1].name > last.name:
                            last = ohlcv.iloc[-1]

        if last is not None:
            self.last_ohlcv = last

        return last

    def feed_trades(self, ex_trades):
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
        last = None

        for ex, syms in ex_trades.items():
            for sym, trades in syms.items():
                if len(trades) > 0:
                    self.trades[ex][sym] = self.trades[ex][sym].append(trades)

                    if not last or trades.iloc[-1].name > last.name:
                        last = trades.iloc[-1]

        if last is not None:
            self.last_trade = last

        return last

    def feed_data(self, ex_ohlcvs, ex_trades, start=None, end=None):
        """ Feed (partial) data from ohlcvs and trades with timestamp between start and end. """
        last_ohlcv = None
        last_trade = None
        prev_ohlcv = self.last_ohlcv

        if not start or not end:  # feed all records in data
            last_ohlcv = self.feed_ohlcv(ex_ohlcvs)
            last_trade = self.feed_trades(ex_trades)
        else:
            partial1 = {}
            for ex, syms in ex_ohlcvs.items():
                partial1[ex] = {}
                for sym, tfs in syms.items():
                    partial1[ex][sym] = {}
                    for tf, ohlcv in tfs.items():
                        rows = select_time(ohlcv, start, end)
                        partial1[ex][sym][tf] = rows

            last_ohlcv = self.feed_ohlcv(partial1)

            partial = {}
            for ex, syms in ex_trades.items():
                partial[ex] = {}
                for sym, trades in syms.items():
                    rows = select_time(trades, start, end)
                    partial[ex][sym] = rows

            last_trade = self.feed_trades(partial)

        dt_ohlcv = last_ohlcv.name if last_ohlcv is not None else None
        dt_trade = last_trade.name if last_trade is not None else None
        max_dt = dt_max(dt_ohlcv, dt_trade)

        self.update_timer(max_dt)
        self._tick()


        if config['mode'] == 'debug':
            ### For checking if data is correct ###
            ### If errors are raised means ohlcv and trade timestamp doesn't match. ###
            # if max_dt is not None:
            #     dt_ohlcv = '' if dt_ohlcv is None else dt_ohlcv
            #     dt_trade = '' if dt_trade is None else dt_trade
            #     logger.debug(f"last ohlcv/trade feeded "
            #                  f"{dt_ohlcv.__str__():<19} || "
            #                  f"{dt_trade.__str__():<19}")

            dt_diff = timedelta(seconds=60)

            if self.last_trade.name - self.last_ohlcv.name > dt_diff:
                # logger.debug(f"trade timestamp {self.last_trade.name} > "
                #              f"ohlcv timestamp {self.last_ohlcv.name} by more than 1 minute")
                raise ValueError(f"trade timestamp {self.last_trade.name} > "
                                 f"ohlcv timestamp {self.last_ohlcv.name} by more than 1 minute")

            if prev_ohlcv is None:
                prev_ohlcv = self.last_ohlcv

            ohlcv_dt_diff = self.last_ohlcv.name - prev_ohlcv.name

            if self.last_ohlcv.name - ohlcv_dt_diff - self.last_trade.name > dt_diff:
                # logger.debug(f"last_ohlcv {ms_dt(self.last_ohlcv.name.timestamp()*1000)}/{self.last_ohlcv.name} > "
                #              f"last_trade {ms_dt(self.last_trade.name.timestamp()*1000)}/{self.last_trade.name} by more than 1 minute")
                raise ValueError(f"last_ohlcv {ms_dt(self.last_ohlcv.name.timestamp()*1000)}/{self.last_ohlcv.name} > "
                                 f"last_trade {ms_dt(self.last_trade.name.timestamp()*1000)}/{self.last_trade.name} by more than 1 minute")

    def update_timer(self, dt):
        if dt is None:
            self.timer.tick()
        else:
            dt = roundup_dt(dt, sec=self.timer.interval_sec())
            self.timer.set_now(dt)

    def _tick(self):
        """ Execute pending orders. """
        self._check_data_feed_time()
        self._execute_orders()

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

    def generate_order(self, ex, market, side, order_type, amount, price=None, *, margin=False):
        """ Helper function for generating order dict for `open`. """
        if order_type == 'limit' and not price:
            raise ValueError("limit orders must provide a price.")

        return {
            'ex': ex,
            'market': market,
            'side': side,
            'order_type': order_type,
            'amount': amount,
            'price': price,
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
                    'price': (if order_type is 'limit')
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
                return None
        else:
            # (order_type: market)
            # Assume the order will be fully executed anyway.
            # Balance will be substracted on order execution.
            self.orders[ex][order['#']] = order
            return order

    def _gen_order(self, order):
        curr = self.trading_balance(order['market'], order['side'], order['margin'])
        price = order['price'] if order['order_type'] == 'limit' else 0
        order = {
            "#": self.order_count(),
            "uuid": gen_id(),
            "ex": order['ex'],
            "market": order['market'],
            "side": order['side'],
            "order_type": order['order_type'],
            "open_time": self.timer.now(),
            "close_time": None,    # filled after closed/canceled/executed
            "price": price,             # open price
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

    def is_valid_order(self, order):
        """ Check fields in the order. """
        order_fields = ['market', 'side', 'order_type', 'amount']

        if order['order_type'] == 'limit':
            order_fields += ['price']

        if not set(order_fields).issubset(order.keys()):
            logger.warn(f"Invalid order {order}")
            return False

        if order['order_type'] == 'limit' and order['price'] == 0:
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

            del self.positions[ex][id]
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
            self.orders_history[ex][id] = order
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

            if is_buy(order):
                self.wallet[ex][curr] += order['amount']
            else:
                self.wallet[ex][curr] += order['amount'] * order['price']

            self.order_history[ex][order['#']] = order
            executed_orders.append(order)

        for ex, orders in self.orders.items():
            for id, order in orders.items():

                # Close margin position
                if order['margin'] and order['active']:
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
                    order['price'] = self.cur_price(ex, order['market'])

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
            logger.warn(f"Not enough balance to open order => "
                        f"{curr}--{self.wallet[ex][curr]}<{cost}")
            return False
        else:
            return True

    def trading_balance(self, market, side, margin):
        curr = ''
        if margin:
            curr = market.split('/')[1]
        elif side == 'buy':
            curr = market.split('/')[1]  # qoute balance
        elif side == 'sell':
            curr = market.split('/')[0]  # base balance
        else:
            raise ValueError("Invalid parameters in `trading_balance`")
        return curr

    def _match_order(self, order):
        cond1 = (self.cur_price(order['ex'], order['market']) == order['price'])
        cond2 = (self.cur_price(order['ex'], order['market']) < order['price'])

        if (cond1)\
        or (is_buy(order) and cond2)\
        or (is_sell(order) and not cond2):
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

    def opposite_currency(self, order):
        currs = order['market'].split('/')
        currs.remove(order['currency'])
        return currs[0]

    def cur_price(self, ex, market):
        return self.trades[ex][market].iloc[-1]['price']

    def order_count(self):
        self._order_count += 1
        return self._order_count

    def _calc_order(self, order):

        if is_buy(order):
            order['cost'] = order['price'] * order['amount']
            order['fee'] = order['price'] * order['amount'] * self.config['fee']
            remain = order['cost'] - order['fee']
            order['amount'] = remain / order['price']
        else:
            order['cost'] = order['amount']
            order['fee'] = order['amount'] * self.config['fee']
            order['amount'] -= order['fee']

    def _calc_margin_order(self, order):
        if not order['active']:  # opening a margin position
            base_amount = order['amount'] / self.config['margin_rate']
            order['margin_fund'] = order['amount'] - base_amount
            order['margin_fee'] = order['margin_fund'] * self.config['margin_fee']
            order['fee'] += order['price'] * order['amount'] * self.config['fee']
            order['cost'] = order['price'] * base_amount + order['fee'] + order['margin_fee']
        else:  # closing a margin position
            order['fee'] += order['price'] * order['amount'] * self.config['fee']
            order['PL'] = self._calc_margin_pl(order)

    def _calc_margin_pl(self, order):
        price_diff = order['close_price'] - order['price']

        if order['side'] == 'sell':
            price_diff *= -1

        pl = price_diff * order['amount'] - order['fee'] - order['margin_fee']
        return pl

    def _calc_margin_return(self, order):
        base_amount = order['amount'] / self.config['margin_rate']
        PL = self._calc_margin_pl(order)
        return_ = order['open_price'] * base_amount + PL


def is_buy(order):
    return True if order['side'] == 'buy' else False


def is_sell(order):
    return True if order['side'] == 'sell' else False
