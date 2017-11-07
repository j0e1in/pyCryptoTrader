from ccxt.base.exchange import Exchange
from datetime import timedelta, datetime
import logging

from utils import combine, sec_ms, ms_sec

INF = 999999999
logger = logging.getLogger()
log = logger.debug


class Backtest():

    def __init__(self, mongo):
        self.mongo = mongo
        self.options = None
        self.settings = {
            "fee": 0.002,
            "margin_gap": 0.005  # +-0.0025*price
        }

    def setup(self, options):
        """ Set options for the next backtest.
            (All options are required.)

            Options
                Required:
                    strategy: function, to give long/short orders
                    exchange: str, exchange name
                    symbol: str, symbol to trade
                    fund: int, amount of initial fund
                    start: str, start timestamp
                    end: str, end timestamp
                Optional:
                    margin: bool, to entabl margin trading or not, default to False
                    data_feed: dict, data request for feeding into strategy, base on timeframe
                        ohlcv: ['1m', '30m', '1h'] (etc.)
        """
        if not self._check_options(options):
            raise ValueError('Backtest options are invalid.')

        options['start_timestamp'] = Exchange.parse8601(options['start'])
        options['end_timestamp'] = Exchange.parse8601(options['end'])
        self.options = options

    async def test(self):
        if not self.options:
            raise ValueError("Use Backtest.setup() to set testing options first. ")

        self.order_id = 0
        self.test_info = combine(self.options, self.settings)

        self.account = {
            "base_balance": 0,
            "qoute_balance": self.options['fund'],
            "open_orders": {}
        }

        self.report = {
            "fund": self.options['fund'],
            "profit_loss": 0,
            "profit_percent": 0,  # *100
            "trades": [],
            "max_profit_trade": {
                "profit_loss": 0
            },
            "max_loss_trade": {
                "profit_loss": 0
            }
        }

        # Load all required data at once
        if self.options['data_feed']:
            self.data_feed = await self.load_data(self.options['data_feed'])

        # If user ask for 1m ohlcv already, use it, otherwise load it mannually.
        if '1m' in self.options['data_feed']['ohlcv']:
            self.price_feed = build_dict_index(self.data_feed['ohlcv']['1m'], idx_col='timestamp')
        else:
            _feed = await build_dict_index(self.load_data({'ohlcv': ['1m']}), idx_col='timestamp')
            self.price_feed = _feed['ohlcv']['1m']

        self.options['strategy'](self)
        self.close_all_orders(self.options['end_timestamp'])

        self.report['profit_loss'] = self.account["qoute_balance"] - self.options['fund']
        self.report['profit_percent'] = self.report['profit_loss'] / self.options['fund']
        return self.report

    def open_order(self, order_type, timestamp, amount):
        price = self.get_price(timestamp)
        cost = price * amount * (1 + self.settings['fee'])

        if price == 0:
            logger.info(f"Open order failed: cannot get price from {timestamp}")
            return False, -1  # return an invalid order_id
        elif cost > self.account['qoute_balance']:
            logger.info(f"Open order failed: no enough balance,"
                        f"[cost] {cost}, [balance] {self.account['qoute_balance']}")
            return False, -1  # return an invalid order_id

        order_id = self.get_order_id()
        order = {
            "order_id": order_id,
            "order_type": order_type,
            "open_timestamp": timestamp,
            "close_timestamp": None,
            "open_price": price,
            "close_price": 0,
            "amount": amount,
            "fee": price * amount * self.settings['fee'],
            "profit_loss": 0
        }
        self.account['qoute_balance'] -= cost
        self.account['open_orders'][order_id] = order
        self.report['trades'].append(order)

        logger.info(f"Open {order['order_type']} order succeed: "
                    f"[time] {datetime.utcfromtimestamp(ms_sec(timestamp))}, "
                    f"[price] {price}, [amount] {amount}")

        log(f"qoute_balance: {self.account['qoute_balance']}")
        return True, order_id

    def close_order(self, order_id, timestamp):
        if order_id not in self.account['open_orders']:
            logger.info(f"Close order failed: no open order_id {order_id}")
            return False

        order = self.account['open_orders'][order_id]
        del self.account['open_orders'][order_id]
        price = self.get_price(timestamp)
        order['close_price'] = price
        order['close_timestamp'] = timestamp
        profit_loss = (order['close_price'] - order['open_price']) * order['amount']

        if order['order_type'] == "short":
            profit_loss *= -1

        order['profit_loss'] = profit_loss
        return_balance = order['amount'] * order['open_price'] + profit_loss
        self.account['qoute_balance'] += return_balance
        self.update_max_profit(order)
        self.update_max_loss(order)

        logger.info(f"Close {order['order_type']} order succeed: "
                    f"[time] {datetime.utcfromtimestamp(ms_sec(timestamp))}, "
                    f"[price] {price}, [amount] {order['amount']}, [PL] {profit_loss}")

        log(f"qoute_balance: {self.account['qoute_balance']}")
        return True

    def close_all_orders(self, timestamp):
        _open_orders = self.account['open_orders'].copy()
        for order_id, order in _open_orders.items():
            self.close_order(order_id, timestamp)

    def get_order_id(self):
        self.order_id += 1
        _id = self.order_id
        return _id

    def get_price(self, timestamp):
        ms_delta = sec_ms(timedelta(minutes=1).seconds)
        ts = timestamp

        while ts >= self.test_info['start_timestamp'] \
                and ts <= self.test_info['end_timestamp']:
            if ts in self.price_feed:
                return self.price_feed[ts]['close']  # use close price
            else:
                ts -= ms_delta
        log(f"Cannot get price at {datetime.utcfromtimestamp(ms_sec(timestamp))}")
        return 0  # Error: cannot find correspondent price

    def update_max_profit(self, order):
        if order['profit_loss'] > self.report['profit_loss']:
            self.report['max_profit_trade'] = order

    def update_max_loss(self, order):
        if order['profit_loss'] < self.report['profit_loss']:
            self.report['max_loss_trade'] = order

    async def load_data(self, data_feed_options):
        """
            data = {
                'ohlcv': {
                    '1m': [[...], [...]],
                    '15m': [[...], [...]]
                }
            }
        """
        data = {}
        exchange = self.options['exchange']
        symbol = self.options['symbol']
        _symbol = ''.join(symbol.split('/'))  # remove '/'
        start = self.options['start_timestamp']
        end = self.options['end_timestamp']

        if 'ohlcv' in data_feed_options:
            data['ohlcv'] = {}
            for tf in data_feed_options['ohlcv']:
                pair = f"{symbol}_{tf}"
                collection = f"{exchange}_ohlcv_{_symbol}_{tf}"
                coll = getattr(self.mongo.client.exchange, collection)
                cursor = coll.find({'timestamp': {'$gte': start, '$lte': end}}, {'_id': 0})\
                             .sort('timestamp', 1)
                data['ohlcv'][tf] = await cursor.to_list(length=INF)

        return data

    # ==================================== #
    #           PRIVATE FUNCTIONS          #
    # ==================================== #

    def _check_options(self, options):
        if ('strategy' not in options or not callable(options['strategy']))       \
                or ('exchange' not in options or not isinstance(options['exchange'], str))\
                or ('symbol' not in options or not isinstance(options['symbol'], str))    \
                or ('fund' not in options or not isinstance(options['fund'], int))        \
                or ('start' not in options or not isinstance(options['start'], str))      \
                or ('end' not in options or not isinstance(options['end'], str)):
            return False
        if ('data_feed' in options and not isinstance(options['data_feed'], dict))\
                or ('margin' in options and not isinstance(options['margin'], bool)):
            return False
        return True


def build_dict_index(data, idx_col):
    """ Extract a column of a list of dict and
        use the column's value as key to build a dict of dicts.
        [{...}, {...}, {...}] > { _:{..}, _:{..}, _:{..} }
    """
    dict_index = {}
    for d in data:
        tmp = d.copy()  # values are referenced, not copied
        del tmp[idx_col]
        dict_index[d[idx_col]] = tmp
    return dict_index
