import copy
import logging
import pandas as pd

from utils import not_implemented, config, gen_id, combine, dt_ms, ms_dt, get_rows_with_timestamp

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

    def init_account(self, funds=None):
        ex_empty_dict = {ex: {} for ex in self.markets}

        if not funds:
            funds = self.config['funds']

        self.account = {
            "wallet": self._init_wallet(funds),
            "orders": copy.deepcopy(ex_empty_dict),                 # active orders
            "order_history": copy.deepcopy(ex_empty_dict),          # inactive orders
            "margin_orders": copy.deepcopy(ex_empty_dict),          # active margin orders
            "margin_order_history": copy.deepcopy(ex_empty_dict),   # inactive margin orders
            "positions": copy.deepcopy(ex_empty_dict)               # active margin positions
        }

        self.wallet = self.account['wallet']
        self.orders = self.account['orders']
        self.order_history = self.account['order_history']
        self.margin_orders = self.account['margin_orders']
        self.margin_order_history = self.account['margin_order_history']
        self.positions = self.account['positions']

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
                ex_ohlcv: contain 3 levels, exchange > timeframe > symbol
                {
                    'bitfinex': {                       # ex
                        '1m': {                         # tf
                            'BTC/USD': DataFrame(...),  # sym, ohlcv
                            'ETH/USD': DataFrame(...),
                        }
                    }
                }
                timeframe: '1m'/'5m'/...
        """
        for ex, syms in ex_ohlcv.items():
            for sym, tfs in syms.items():
                for tf, ohlcv in tfs.items():
                    self.ohlcvs[ex][sym][tf] = \
                        self.ohlcvs[ex][sym][tf].append(ohlcv)

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
        for ex, syms in ex_trades.items():
            for sym, trades in syms.items():
                self.trades[ex][sym] = self.trades[ex][sym].append(trades)

    def feed_data(self, start, end, ex_ohlcvs, ex_trades):
        """ Feed data from ohlcvs and trades with timestamp between start and end. """
        partial = {}

        for ex, syms in ex_ohlcvs.items():
            partial[ex] = {}
            for sym, tfs in syms.items():
                partial[ex][sym] = {}
                for tf, ohlcv in tfs.items():
                    rows = get_rows_with_timestamp(ohlcv, start, end)
                    partial[ex][sym][tf] = rows

        self.feed_ohlcv(partial)

        partial = {}

        for ex, syms in ex_trades.items():
            partial[ex] = {}
            for sym, trades in syms.items():
                rows = get_rows_with_timestamp(trades, start, end)
                partial[ex][sym] = rows

        self.feed_trades(partial)

    def open(self, ex, order, margin=False):
        """ Open an order to the market, will be executed on the next tick if price exceeds.
            Currently surpported order_type: limit, market
            Param
                order: {
                    'market':
                    'side':
                    'order_type':
                    'amount':
                    'price': (if order_type is 'limit')
                }
        """
        if not self.is_valid_order(order, margin):
            return None

        order = self._gen_order(ex, order, margin)
        if order['order_type'] == 'limit':
            if self.has_enough_balance(ex, order['curr'], order['cost']):
                self.wallet[ex][order['curr']] -= order['cost']
                self.orders[ex][order['id']] = order
                return order['id']
            else:
                return None
        else:
            # (order_type: market)
            # Assume the order will be fully executed anyway.
            # Balance will be substracted on order execution.
            self.orders[ex][order['id']] = order
            return order['id']

    def _gen_order(self, ex, order, margin):
        curr = self.trading_balance(order['market'], order['side'], order['margin'])
        price = order['price'] if order['order_type'] == 'limit' else 0
        order = {
            "id": gen_id(),
            "ex": ex,
            "market": order['market'],
            "side": order['side'],
            "order_type": order['order_type'],
            "open_timestamp": self.get_timestamp(),
            "close_timestamp": None,    # filled after closed/canceled/executed
            "price": price,             # open price
            "amount": order['amount'],
            "currency": curr,
            "cost": 0,                  # filled before open
            "fee": 0,                   # filled before open
            "canceled": False,          # filled after canceled
            "margin": margin,
        }
        margin_order = {
            "active": False,
            "margin_fee": 0,            # filled before open if "margin" is True
            "margin_fund": 0,           # filled before open if "margin" is True
            "close_price": 0,           # filled after closed
            "PL": 0,                    # filled after closed
        }

        if margin:
            order = combine(order, margin_order)

        if order['order_type'] == 'limit':
            if not margin:
                self._calc_order(order)
            else:
                self._calc_margin_order(order)

        return order

    def is_valid_order(self, order):
        order_fields = ['market', 'side', 'order_type', 'amount']

        if order['order_type'] == 'limit':
            order_fields += ['price']

        if not set(margin_order_fields).issubset(order.keys()):
            logger.warn(f"Invalid order {order}")
            return False

        if order['order_type'] == 'limit' and order['price'] == 0:
            logger.warn(f"Cannot open order at price 0")
            return None

        return True

    def close_position(self, ex, id):
        if id in self.positions[ex]:
            order = self.positions[ex][id]

            # queue the order to activate order again for trader to execute
            self.orders[ex][id] = order

            del self.positions[ex][id]
            return order
        else:
            return None

    def cancel_order(self, ex, id):
        if id in self.orders[ex]:
            order = self.orders[ex][id]
            order['canceled'] = True
            order['close_timestamp'] = self.get_timestamp()

            self.wallet[ex][order['currency']] += order['cost']
            self.orders_history[ex][id] = order
            del self.orders[ex][id]
            return order
        else:
            return None

    def close_all_positions(self, ex):
        orders = []
        for id in self.positions[ex]:
            orders.append(self.close_position(ex, id))
        return orders

    def cancel_all_orders(self, ex):
        orders = []
        for id in self.orders[ex]:
            orders.append(self.cancel_order(ex, id))
        return orders

    def tick(self):
        """ Call this method after feeding data
            to the point where (timestamp <= next timer tick),
            representing exchanges feed new data.
        """
        self.timer.tick()
        self._check_data_feed_timestamp()
        self._execute_orders()

    def _check_data_feed_timestamp(self):
        cur_timestamp = self.timer.tsnow()
        for ex, syms in self.ohlcvs:
            for market, tfs in syms:
                for tf, ohlcv in tfs:
                    if dt_ms(ohlcv[-1]['timestamp']) > cur_timestamp:
                        raise ValueError(f"ohlcv feed's timestamp exceeds timer's.")

        for ex, syms in self.trades:
            for market, trades in syms:
                if dt_ms(trades[-1]['timestamp']) > cur_timestamp:
                    raise ValueError(f"trades feed's timestamp exceeds timer's.")

    def _execute_orders(self):
        """ Execute orders in queue.
            If order_type is 'limit', it will check if current price exceeds the target.
            If order_type is 'market', it will execute at current price if balance is enough.
        """
        executed_orders = []

        def execute_open_position(order):
            order['active'] = True
            self.positions[ex][id] = order
            del self.orders[ex][order['id']]
            executed_orders.append(order)

        def execute_close_position(order):
            ex = order['ex']
            order['close_price'] = self.cur_price(ex, order['market'])
            order['close_timestamp'] = self.get_timestamp()
            order['active'] = False
            self._calc_margin_order(order)
            self.wallet[ex][order['currency']] += self._calc_margin_return(order)
            del self.positions[ex][order['id']]
            executed_orders.append(order)

        def execute_normal_order(order):
            order['close_timestamp'] = self.get_timestamp()
            curr = self.opposite_currency(order)
            self.wallet[ex][curr] += order['amount']
            self.order_history[ex][id] = order
            del self.orders[ex][id]
            executed_orders.append(order)

        for ex, orders in self.orders.items():
            for id, order in orders:

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

                        if self.has_enough_balance(ex, order['curr'], order['cost']):
                            self.wallet[ex][order['currency']] -= order['cost']
                            execute_open_position(order)
                        else:
                            logger.warn(f"Not enough balance to open margin position: {order}")
                            self.cancel_order(order)

                    else:  # normal order
                        self._calc_order(order)

                        if self.has_enough_balance(ex, order['curr'], order['cost']):
                            self.wallet[ex][order['currency']] -= order['cost']
                            execute_normal_order(order)
                        else:
                            logger.warn(f"Not enough balance to execute normal market order: {order}")
                            self.cancel_order(order)

        for order in executed_orders:
            del self.orders[ex][order['id']]
            if not (margin and order['active']):  # if not an open position order
                self.order_history[ex][order['id']] = order

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
        cond1 = (self.cur_price(order['ex'], order['currency']) == order['price'])
        cond2 = (self.cur_price(order['ex'], order['currency']) > order['price'])

        if (cond1)\
                or (order['side'] == 'buy' and cond)\
                or (order['side'] == 'sell' and not cond):
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
        currs -= [order['currency']]
        return currs[0]

    def get_timestamp(self):
        return self.timer.tsnow()

    def cur_price(self, ex, symbol):
        return self.trades[ex][symbol].loc[-1]

    def _calc_order(self, order):
        order['fee'] = order['price'] * order['amount'] * self.config['fee']
        order['cost'] = order['price'] * order['amount'] + order['fee']

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
