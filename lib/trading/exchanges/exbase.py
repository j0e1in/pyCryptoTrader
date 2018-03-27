from asyncio import ensure_future
from datetime import datetime, timedelta
from pprint import pprint

import asyncio
import ccxt.async as ccxt
import inspect
import logging

from analysis.hist_data import fetch_ohlcv
from utils import \
    config, \
    utc_now, \
    roundup_dt, \
    rounddown_dt, \
    ex_name, \
    tf_td, \
    rsym, \
    ms_dt, \
    MIN_DT, \
    not_implemented, \
    init_ccxt_exchange, \
    execute_mongo_ops, \
    handle_ccxt_request, \
    is_within

logger = logging.getLogger('pyct')


class EXBase():
    """ Unifiied exchange interface for trader.
        Available attributes / methods:
        - Attreibutes:
            exname
            markets
            markets_info
            orderbook
            tickers
            timeframes
            wallet

        - Methods
            start
            get_deposit_address
            get_new_deposit_address
            fetch_order
            fetch_open_orders
            fetch_closed_orders
            fetch_my_trades
            update_ticker
            update_markets
            update_wallet
            create_order
            cancel_order
            withdraw


        ** Note: ohlcv and trades can be retreived from db
    """

    def __init__(self, mongo, ex_id, apikey=None, secret=None,
                 custom_config=None, ccxt_verbose=False, log=False,
                 disable_ohlcv_stream=False, notifier=None):
        self.mongo = mongo
        self.exname = ex_name(ex_id)
        self.apikey = apikey
        self.secret = secret
        self.log = log
        self.disable_ohlcv_stream = disable_ohlcv_stream
        self.notifier = notifier

        self._config = custom_config if custom_config else config
        self.config = self._config['ccxt']

        self.ex = init_ccxt_exchange(ex_id, apikey, secret,
                                     verbose=ccxt_verbose,
                                     timeout=self._config['request_timeout'])

        self.markets = self._config['trading'][self.exname]['markets']
        self.timeframes = self._config['trading'][self.exname]['timeframes']
        self.trade_fees = {}
        self.withdraw_fees = {}
        self.markets_info = {}
        self.orderbook = {}
        self.tickers = {}
        self.wallet = self.init_wallet()
        self.ready = {
          'ohlcv': False,
          'trade': False,
          'orderbook': False,
          'markets': False,
          'wallet': False,
          'trade_fees': False,
          'withdraw_fees': False,
        }

        self.ohlcv_start_end = {}
        self.markets_start_dt = {}

    def init_wallet(self):
        wallet = {}
        wallet['USD'] = 0
        for market in self._config['trading'][self.exname]['markets']:
            wallet[market.split('/')[0]] = 0
        return wallet

    def is_ready(self):
        """ Return True if data streams are up-to-date. """
        for task, ready in self.ready.items():
            if not ready:
                return False
        return True

    def start_tasks(self, data_streams=['ohlcv']):
        """ Start data streams and load account data.
            Trader can only use EX instance if it's started and ready.
            Param
                data_streams: list, 'ohlcv'/'trade'/'orderbook'
                log: bool, if True, log data stream actions
        """
        tasks = []
        if 'ohlcv' in data_streams \
        and not self.disable_ohlcv_stream:
            tasks.append(self._start_ohlcv_stream())
        else:
            self.ready['ohlcv'] = True

        if 'trade' in data_streams:
            tasks.append(self._start_trade_stream())
        else:
            self.ready['trade'] = True

        if 'orderbook' in data_streams:
            tasks.append(self._start_orderbook_stream())
        else:
            self.ready['orderbook'] = True

        tasks.append(self.load_markets())
        tasks.append(self.update_markets())
        tasks.append(self.update_wallet())
        tasks.append(self.update_trade_fees())
        tasks.append(self.update_withdraw_fees())

        return tasks

    async def _start_ohlcv_stream(self):

        async def fetch_ohlcv_to_mongo(symbol, start, end, timeframe):
            ops = []

            collname = f"{self.exname}_ohlcv_{rsym(symbol)}_{timeframe}"
            coll = self.mongo.get_collection(self._config['database']['dbname_exchange'], collname)
            res = fetch_ohlcv(self.ex, symbol, start, end, timeframe, log=self.log)

            async for ohlcv in res:

                if len(ohlcv) is 0:
                    break

                # [ MTS, OPEN, CLOSE, HIGH, LOW, VOLUME ]
                for oh in ohlcv:
                    tmp = {
                        'timestamp': oh[0],
                        'open':      oh[1],
                        'high':      oh[2],
                        'low':       oh[3],
                        'close':     oh[4],
                        'volume':    oh[5]
                    }
                    ops.append(
                        ensure_future(
                            coll.update_one(
                                {'timestamp': tmp['timestamp']},
                                {'$set': tmp},
                                upsert=True)))

                await execute_mongo_ops(ops)

        logger.info("Start ohlcv data stream")
        last_update = MIN_DT

        while True:
            await self.update_ohlcv_start_end()

            if is_within(last_update, timedelta(seconds=10)):
                await asyncio.sleep(5)

            tf = '1m'
            td = tf_td(tf)

            # Fetch only 1m ohlcv
            for market in self.markets:

                if market in self.ohlcv_start_end:
                    end = self.ohlcv_start_end[market][tf]['end']
                    cur_time = rounddown_dt(utc_now(), td)

                    if end < cur_time:
                        # Fetching one-by-one is faster and safer(from blocking)
                        # than gathering all tasks at once
                        await fetch_ohlcv_to_mongo(market, end, cur_time, tf)

            last_update = utc_now()

            if await self.is_ohlcv_uptodate():
                self.ready['ohlcv'] = True
                fetch_interval = timedelta(seconds=self.config['ohlcv_fetch_interval'])
                countdown = roundup_dt(utc_now(), fetch_interval) - utc_now()

                # 1. Sleep will be slighly shorter than expected
                # 2. Add extra seconds because exchange server data preperation may delay
                await asyncio.sleep(countdown.seconds + 40)

    async def _start_trade_stream(self):
        # TODO
        not_implemented()

    async def _start_orderbook_stream(self, params={}):
        """ Fetch orderbook periodically. May not be needed if using `get_orderbook`."""
        logger.info("Start orderbook data stream")

        while True:
            for market in self.markets:
                self.orderbook[market] = await self._fetch_orderbook(market, params=params)

            self.ready['orderbook'] = True
            await asyncio.sleep(self.config['orderbook_delay'])

    async def update_my_trades(self):
        """ Keep history trades in mongodb up-to-date. """

        for market in self.markets:
            last_trade = await self.mongo.get_my_last_trade(self.exname, market)

            if last_trade:
                start = last_trade['datetime'] - timedelta(days=3)
            else:
                start = MIN_DT

            end = utc_now()

            # Fetch recent trades to mongo
            await self.fetch_my_recent_trades(market, start, end)

    async def get_orderbook(self, symbol, params={}):
        """ Fetch orderbook of a specific symbol on-demand.
            ccxt response:
            {'asks': [[13534.0, 1.2373243],
                      [13535.0, 2.42267671],
                      [13537.0, 0.11326825],
                      [13549.0, 1.2337],
                      [13550.0, 0.54822278],
                       ... ],
             'bids': [[13531.0, 0.00375997],
                      [13530.0, 0.3],
                      [13527.0, 0.011],
                      [13522.0, 0.502],
                      [13521.0, 0.0758],
                       ... ],
             'datetime': '2018-01-12T09:30:20.636Z',
             'timestamp': 1515749419636}
        """
        self.orderbook[symbol] = await self._fetch_orderbook(symbol, params=params)
        return self.orderbook[symbol]

    async def get_market_price(self, symbol):
        """ Get current price from orderbook. """
        orderbook = await self.get_orderbook(symbol)
        return {
            'buy': orderbook['bids'][0][0],
            'sell': orderbook['asks'][0][0],
        }

    async def _fetch_orderbook(self, symbol, params={}):
        if self.log:
            logger.info(f"Fetching {symbol} orderbook")

        orderbook = await handle_ccxt_request(self.ex.fetch_order_book, symbol, params=params)
        orderbook['datetime'] = ms_dt(orderbook['timestamp'])
        return orderbook

    async def update_ticker(self):
        """
            ccxt response:
            {'AVT/BTC':
                {'ask': 0.0004183,
                 'average': 0.00041231,
                 'baseVolume': 69254.65426089,
                 'bid': 0.00040632,
                 'change': None,
                 'close': None,
                 'datetime': '2018-01-12T10:54:20.785Z',
                 'first': None,
                 'high': 0.00043988,
                 'info': {'ask': '0.0004183',
                          'bid': '0.00040632',
                          'high': '0.00043988',
                          'last_price': '0.00041',
                          'low': '0.0003452',
                          'mid': '0.00041231',
                          'pair': 'AVTBTC',
                          'timestamp': '1515754459.785556691',
                          'volume': '69254.65426089'},
                 'last': 0.00041,
                 'low': 0.0003452,
                 'open': None,
                 'percentage': None,
                 'quoteVolume': None,
                 'symbol': 'AVT/BTC',
                 'timestamp': 1515754459785.557,
                 'vwap': None},
            ...}
        """
        res = await handle_ccxt_request(self.ex.fetch_tickers)
        for market in self.markets:
            if market in res:
                self.tickers[market] = res[market]
        return self.tickers

    async def load_markets(self):
        await handle_ccxt_request(self.ex.load_markets)

    async def update_markets(self):
        not_implemented()

    #####################
    # AUTHENTICATED API #
    #####################

    async def update_wallet(self):
        """
            ccxt response: (bitfinex)
            {'BCH': {'free': 0.00441364, 'total': 0.00441364, 'used': 0.0},
             'BTC': {'free': 0.0051689, 'total': 0.0051689, 'used': 0.0},
             'USD': {'free': 0.0, 'total': 0.0, 'used': 0.0},
             'free': {'BCH': 0.00441364, 'BTC': 0.0051689, 'USD': 0.0},
             'info': [{'amount': '0.00441364',
                       'available': '0.00441364',
                       'currency': 'bch',
                       'type': 'exchange'},
                      {'amount': '0.0051689',
                       'available': '0.0051689',
                       'currency': 'btc',
                       'type': 'exchange'},
                      {'amount': '0.0',
                       'available': '0.0',
                       'currency': 'usd',
                       'type': 'exchange'}],
             'total': {'BCH': 0.00441364, 'BTC': 0.0051689, 'USD': 0.0},
             'used': {'BCH': 0.0, 'BTC': 0.0, 'USD': 0.0}}
        """
        self._check_auth()

        if self.log:
            logger.info("Updating wallet")

        res = await handle_ccxt_request(self.ex.fetch_balance)

        for curr, amount in res['free'].items():
            self.wallet[curr] = float(amount)

        self.ready['wallet'] = True
        return self.wallet

    async def get_balance(self, curr, type=None):
        """ Child classes should override this method to adapt to its wallet structure.
            Default has no type.
            Params
                curr: str, eg. 'USD', 'BTC', ...
                type: str, eg. 'exchange', 'margin', 'funding' etc.
        """
        return self.wallet[curr]

    async def get_deposit_address(self, currency, type=None):
        self._check_auth()
        res = await handle_ccxt_request(self.ex.fetch_deposit_address, currency)
        return res['address']

    async def get_new_deposit_address(self, currency, type=None):
        """ Generate a new address despite an old one is already existed. """
        self._check_auth()
        res = await handle_ccxt_request(self.ex.create_deposit_address, currency)
        return res['address']

    async def fetch_open_orders(self, symbol=None):
        not_implemented()

    async def fetch_closed_orders(self,  symbol=None):
        not_implemented()

    async def fetch_order(self):
        """ Fetch a single order using order known id. """
        not_implemented()

    async def fetch_positions(self):
        not_implemented()

    async def fetch_my_recent_trades(self, symbol, start=None, end=None):
        not_implemented()

    async def create_order(self):
        not_implemented()

    async def create_order_multi(self):
        not_implemented()

    async def cancel_order(self):
        not_implemented()

    async def cancel_order_multi(self):
        not_implemented()

    async def cancel_order_all(self):
        not_implemented()

    async def withdraw(self):
        not_implemented()

    async def update_trade_fees(self):
        not_implemented()

    async def update_withdraw_fees(self):
        not_implemented()

    async def transfer_funds(self):
        pass # most exchanges do not support, so just ignore it

    ##############################
    # EXCHANGE UTILITY FUNCTIONS #
    ##############################

    def is_authed(self):
        return True if self.apikey and self.secret else False

    def _check_auth(self):
        if not self.is_authed():
            raise ccxt.AuthenticationError(f"Both API key and secret are required for ``{inspect.stack()[1][3]}``")

    async def update_ohlcv_start_end(self):
        # Get available ohlcv start / end datetime in db
        self.ohlcv_start_end = {}

        for market in self.markets:
            tf = '1m'

            self.ohlcv_start_end[market] = {}
            self.ohlcv_start_end[market][tf] = {}

            start = await self.mongo.get_ohlcv_start(self.exname, market, tf)
            end = await self.mongo.get_ohlcv_end(self.exname, market, tf)

            self.ohlcv_start_end[market][tf]['start'] = start
            self.ohlcv_start_end[market][tf]['end'] = end

    ###############################
    # CUSTOM FUNCTIONS FOR TRADER #
    ###############################

    async def calc_wallet_value(self):
        """ Calculate total value of all currencies using latest 1m ohlcv. """
        not_implemented()

    async def calc_order_value(self):
        not_implemented()

    async def calc_all_position_value(self):
        not_implemented()

    async def calc_trade_fee(self, start, end):
        """ Calcullate total trade fee in a period using history trades. """
        trades = await self.mongo.get_my_trades(self.exname, start, end)
        fee = 0

        for tr in trades:
            fee += tr['fee']

        return fee

    def calc_margin_fee(self, start, end):
        """ Calcullate total margin fee in a period using history orders and trades. """
        # TODO: Find a way to get margin fee
        return 0

    async def calc_account_value(self):
        wallet_value = await self.calc_wallet_value()
        order_value = await self.calc_order_value()
        position_value = await self.calc_all_position_value()
        return wallet_value + order_value + position_value

    async def calc_value_of(self, curr, amount):
        if curr == 'USD' or amount == 0:
            return amount

        sym = curr + '/USD'
        ohlcv = await self.mongo.get_last_ohclv(self.exname, sym, '1m')

        if not ohlcv:
            return 0
        else:
            return ohlcv['close'] * amount

    def set_market_start_dt(self, market, dt):
        self.markets_start_dt[market] = dt

    async def is_ohlcv_uptodate(self):
        await self.update_ohlcv_start_end()

        td = timedelta(seconds=self.config['ohlcv_fetch_interval'])

        for market in self.markets:
            end = self.ohlcv_start_end[market]['1m']['end']
            cur_time = rounddown_dt(utc_now(), td)

            if end < cur_time:
                return False

        return True
