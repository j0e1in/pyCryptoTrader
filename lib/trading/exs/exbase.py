from pprint import pprint
from asyncio import ensure_future
import asyncio
import copy
import ccxt.async as ccxt
import logging
import inspect

from analysis.hist_data import fetch_ohlcv
from utils import combine, \
    config, \
    utc_now, \
    roundup_dt, \
    rounddown_dt, \
    ex_name, \
    timeframe_timedelta, \
    rsym, \
    ms_dt, \
    dt_ms, \
    not_implemented, \
    init_ccxt_exchange, \
    execute_mongo_ops, \
    sec_ms, \
    handle_ccxt_request

from ipdb import set_trace as trace

logger = logging.getLogger()


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
                 custom_config=None, ccxt_verbose=False, log=False):
        self.mongo = mongo
        self.exname = ex_name(ex_id)
        self.apikey = apikey
        self.secret = secret
        self.log = log

        self._config = custom_config if custom_config else config
        self.config = self._config['ccxt']

        self.ex = init_ccxt_exchange(ex_id, apikey, secret,
                                     verbose=ccxt_verbose,
                                     timeout=self._config['request_timeout'])

        self.markets = self._config['trading'][self.exname]['markets']
        self.timeframes = self._config['trading'][self.exname]['timeframes']

        self.trade_fees = {'datetime': None}
        self.withdraw_fees = {'datetime': None}
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
        if 'ohlcv' in data_streams:
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

        tasks.append(self.update_markets())
        tasks.append(self.update_wallet())
        tasks.append(self.update_trade_fees())
        tasks.append(self.update_withdraw_fees())

        return tasks

    async def _start_ohlcv_stream(self):

        async def fetch_ohlcv_to_mongo(symbol, start, end, timeframe):
            ops = []
            count = 0

            collname = f"{self.exname}_ohlcv_{rsym(symbol)}_{timeframe}"
            coll = self.mongo.get_collection('exchange', collname)
            res = fetch_ohlcv(self.ex, symbol, start, end, timeframe, log=self.log)

            async for ohlcv in res:
                processed_ohlcv = []

                if len(ohlcv) is 0:
                    break

                # [ MTS, OPEN, CLOSE, HIGH, LOW, VOLUME ]
                for rec in ohlcv:
                    processed_ohlcv.append({
                        'timestamp': rec[0],
                        'open':      rec[1],
                        'high':      rec[2],
                        'low':       rec[3],
                        'close':     rec[4],
                        'volume':    rec[5]
                    })

                ops.append(ensure_future(coll.insert_many(processed_ohlcv, ordered=False)))

                # insert 1000 ohlcv per op, clear up task stack periodically
                if len(ops) > 50:
                    await execute_mongo_ops(ops)
                    ops = []

            await execute_mongo_ops(ops)

        async def is_uptodate(ohlcv_start_end):
            await self.update_ohlcv_start_end()

            for market in self.markets:
                for tf in self.timeframes:

                    td = timeframe_timedelta(tf)
                    # cur_time = rounddown_dt(utc_now(), sec=td.seconds)
                    end = self.ohlcv_start_end[market][tf][1]

                    if end < cur_time:
                        return False

            return True

        logger.info("Starting ohlcv data stream...")
        self.ohlcv_start_end = {}

        while True:
            await self.update_ohlcv_start_end()

            for market in self.markets:
                for tf in self.timeframes:

                    td = timeframe_timedelta(tf)
                    end = self.ohlcv_start_end[market][tf][1]
                    cur_time = rounddown_dt(utc_now(), sec=td.seconds)

                    if end < cur_time:
                        # Fetching one-by-one is faster and safer(from blocking)
                        # than gather all tasks at once
                        await fetch_ohlcv_to_mongo(market, end, cur_time, tf)

            if await is_uptodate(self.ohlcv_start_end):
                self.ready['ohlcv'] = True
                countdown = roundup_dt(utc_now(), min=1) - utc_now()

                # Sleep will be slighly shorter than expected
                # Add extra seconds because exchange server data preperation may delay
                await asyncio.sleep(countdown.seconds + 8)

    async def _start_trade_stream(self, symbol):
        # TODO
        not_implemented()

    async def _start_orderbook_stream(self, params={}):
        """ Fetch orderbook passively. May not be needed if using `get_orderbook`."""
        logger.info("Starting orderbook data stream...")

        while True:
            for market in self.markets:
                self.orderbook[market] = await self._fetch_orderbook(market, params=params, log=self.log)

            self.ready['orderbook'] = True
            await asyncio.sleep(self.config['orderbook_delay'])

    async def update_my_trades(self, symbol):
        """ Keep history trades in mongodb up-to-date. """
        # TODO
        not_implemented()

        # if not self.ex.hasFetchMyTrades:
        #     logger.warn(f"{self.exname} doesn't have fetch_my_trades method.")
        #     return

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
        self.orderbook[symbol] = await self._fetch_orderbook(symbol, params=params, log=self.log)
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
            logger.info("Updating wallet...")

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

    async def fetch_order(self, id):
        """ Fetch a single order using order known id. """
        not_implemented()

    async def fetch_positions(self):
        not_implemented()

    async def fetch_my_recent_trades(self):
        not_implemented()

    async def create_order(self):
        not_implemented()

    async def cancel_order(self):
        not_implemented()

    async def cancel_order_multi(self, ids):
        not_implemented()

    async def cancel_order_all(self):
        not_implemented()

    async def withdraw(self):
        not_implemented()

    async def withdraw_fees(self):
        not_implemented()

    async def trade_fees(self):
        not_implemented()

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
            self.ohlcv_start_end[market] = {}

            for tf in self.timeframes:
                start = await self.mongo.get_ohlcv_start(self.exname, market, tf)
                end = await self.mongo.get_ohlcv_end(self.exname, market, tf)
                self.ohlcv_start_end[market][tf] = (start, end)

    ###############################
    # CUSTOM FUNCTIONS FOR TRADER #
    ###############################

    def calc_wallet_value(self):
        """ Calculate total value of all currencies using latest 1m ohlcv. """
        not_implemented()

    def calc_trade_fee(self, start, end):
        """ Calcullate total trade fee in a period using history trades. """
        not_implemented()

    def calc_margin_fee(self, start, end):
        """ Calcullate total margin fee in a period using history orders and trades. """
        not_implemented()

