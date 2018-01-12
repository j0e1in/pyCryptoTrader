from pprint import pprint
from asyncio import ensure_future
from pymongo.errors import BulkWriteError
import asyncio
import copy
import ccxt.async as ccxt
import logging

from analysis.hist_data import fetch_ohlcv
from utils import combine, \
    config, \
    utc_now, \
    rounddown_dt, \
    ex_name, \
    get_keys, \
    timeframe_timedelta, \
    rsym, \
    ms_dt, \
    not_implemented

from ipdb import set_trace as trace


logger = logging.getLogger()


class EXBase():
    """ Unifiied exchange interface for trader. """

    def __init__(self, mongo, ex_id, apikey=None, secret=None, custom_config=None):
        self.mongo = mongo
        self.exname = ex_name(ex_id)
        self.apikey = apikey
        self.secret = secret

        self.ex = self.init_ccxt_exchange(ex_id, self.apikey, self.secret)

        self._config = custom_config if custom_config else config
        self.config = self._config['ccxt']

        self.markets = self._config['trading'][self.exname]['markets']
        self.timeframes = self._config['trading'][self.exname]['timeframes']

        self.tickers = {}
        self.markets_info = {}
        self.streams_ready = {}
        self.wallet = self.init_wallet()

    @staticmethod
    def init_ccxt_exchange(ex_id, apikey=None, secret=None):
        """ Return an initialized ccxt API instance. """
        options = combine({
            'enableRateLimit': True,
            'rateLimit': config['ccxt']['rate_limit'],
            'apikey': apikey,
            'secret': secret,
        }, get_keys()[ex_id])

        ex = getattr(ccxt, ex_id)(options)
        return ex

    def init_wallet(self):
        wallet = {}
        wallet['USD'] = 0
        for market in self._config['trading'][self.exname]['markets']:
            wallet[market.split('/')[0]] = 0
        return wallet

    def is_ready(self):
        """ Return True if data streams are up-to-date. """
        for _, ready in self.streams_ready.items():
            if not ready:
                return False
        return True

    async def start(self, data_streams=['ohlcv'], log=False):
        """ Start data streams and load account data.
            Trader can only use EX instance if it's started and ready.
        """
        streams = []
        if 'ohlcv' in data_streams:
            streams.append(ensure_future(self._start_ohlcv_stream(log)))
            self.streams_ready['ohlcv'] = False

        if 'trade' in data_streams:
            streams.append(self._start_trade_stream(log))
            self.streams_ready['trade'] = False

        if 'orderbook' in data_streams:
            streams.append(self._start_orderbook_stream(log))
            self.streams_ready['orderbook'] = False

        await asyncio.gather(*streams)

        await self.update_markets()
        await self.update_wallet()

    async def _start_ohlcv_stream(self, log=False):

        async def fetch_ohlcv_to_mongo(symbol, start, end, timeframe):
            ops = []
            count = 0

            collname = f"{self.exname}_ohlcv_{rsym(symbol)}_{timeframe}"
            coll = self.mongo.get_collection('exchange', collname)
            res = fetch_ohlcv(self.ex, symbol, start, end, timeframe, log=log)

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
                    await self._exec_mongo_op(asyncio.gather, *ops)
                    ops = []

            await self._exec_mongo_op(asyncio.gather, *ops)

        async def is_uptodate(ohlcv_start_end):
            await self.update_ohlcv_start_end()

            for market in self.markets:
                for tf in self.timeframes:

                    td = timeframe_timedelta(tf)
                    cur_time = rounddown_dt(utc_now(), sec=td.seconds)
                    end = self.ohlcv_start_end[market][tf][1]

                    if end < cur_time:
                        return False

            return True

        self.ohlcv_start_end = {}
        ready = True

        while True:
            await self.update_ohlcv_start_end()

            for market in self.markets:
                for tf in self.timeframes:

                    td = timeframe_timedelta(tf)
                    cur_time = rounddown_dt(utc_now(), sec=td.seconds)
                    end = self.ohlcv_start_end[market][tf][1]

                    if end < cur_time:
                        ready = False
                        await fetch_ohlcv_to_mongo(market, end, cur_time, tf)

            if await is_uptodate(self.ohlcv_start_end):
                self.streams_ready['ohlcv'] = True
                await asyncio.sleep(self.config['ohlcv_delay']/8)

    async def _start_trade_stream(self, log=False):
        # TODO
        pass

    async def _start_orderbook_stream(self, log=False, params={}):
        """
            ccxt response:
            {'asks': [[117.54, 8.39429112],
                      [117.55, 16.78858223],
                       ...],
             'bids': [[117.19, 1.02399284],
                       [116.0, 0.5415143]
                       ...],
             'datetime': '2018-01-12T09:30:20.636Z',
             'timestamp': 1515749419636}
        """
        self.orderbooks = {}

        while True:
            for market in self.markets:
                if log:
                    logger.info(f"Fetching {market} orderbook")

                self.orderbooks[market] = await self._send_ccxt_request(self.ex.fetch_order_book, market, params=params)
                self.orderbooks[market]['datetime'] = ms_dt(self.orderbooks[market]['timestamp'])

            await asyncio.sleep(self.config['orderbook_delay'])

    async def update_ticker(self, log=False):
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
                ...
            }
        """
        res = await self._send_ccxt_request(self.ex.fetch_tickers)
        for market in self.markets:
            if market in res:
                self.tickers[market] = res[market]
        return self.tickers

    def update_markets(self):
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
        if not self.isauth():
            raise ValueError(f"API key and secret are required")

        res = await self._send_ccxt_request(self.ex.fetch_balance)

        for curr, amount in res['free'].items():
            self.wallet[curr] = amount

        return self.wallet

    async def _send_ccxt_request(self, func, *args, **kwargs):

        def is_empty_response(err):
            return True if 'empty response' in str(err) else False

        wait = config['ccxt']['wait']
        succ = False
        count = 0

        while not succ:
            if count > self.config['max_retry']:
                logger.error(f"{func} exceeds max retry times")
                return None

            count += 1
            try:
                res = await func(*args, **kwargs)

            except (ccxt.RequestTimeout,
                    ccxt.DDoSProtection,
                    ccxt.ExchangeNotAvailable) as error:

                if is_empty_response(error):  # finished fetching all ohlcv
                    break
                elif isinstance(error, ccxt.ExchangeError):
                    raise error

                logger.info(f'# {type(error).__name__} # retrying in {wait} seconds...')
                await asyncio.sleep(wait)

            else:
                succ = True

        return res

    def isauth(self):
        return True if self.apikey and self.secret else False

    async def update_ohlcv_start_end(self):
        # Get available ohlcv start / end datetime in db
        self.ohlcv_start_end = {}
        for market in self.markets:
            self.ohlcv_start_end[market] = {}

            for tf in self.timeframes:
                start = await self.mongo.get_ohlcv_start(self.exname, market, tf)
                end = await self.mongo.get_ohlcv_end(self.exname, market, tf)
                self.ohlcv_start_end[market][tf] = (start, end)

    @staticmethod
    async def _exec_mongo_op(func, *args, **kwargs):
        try:
            await func(*args, **kwargs)
        except BulkWriteError as err:
            for msg in err.details['writeErrors']:
                if 'duplicate' in msg['errmsg']:
                    continue
                else:
                    if self._config['mode'] == 'debug':
                        pprint("Mongodb BulkWriteError:")
                        pprint(err.details)
                    raise BulkWriteError(err)


class bitfinex(EXBase):

    def __init__(self, mongo, apikey=None, secret=None, custom_config=None):
        super().__init__(mongo, 'bitfinex', apikey, secret, custom_config)

    def init_wallet(self):
        tmp = {'exchange': 0, 'margin': 0, 'funding': 0}

        wallet = {}
        wallet['USD'] = copy.deepcopy(tmp)

        for market in self._config['trading'][self.exname]['markets']:
            wallet[market.split('/')[0]] = copy.deepcopy(tmp)

        return wallet

    async def update_wallet(self):
        res = await self._send_ccxt_request(self.ex.fetch_balance)

        for curr in res['info']:
            sym = str.upper(curr['currency'])

            if sym not in self.wallet:
                self.wallet[sym] = {'exchange': 0, 'margin': 0, 'funding': 0}

            self.wallet[sym][curr['type']] = curr['available']

        return self.wallet

    async def _start_orderbook_stream(self, log=False):
        params = {
            'limit_bids': self.config['orderbook_size'],
            'limit_asks': self.config['orderbook_size'],
            'group': 1,
        }
        await super()._start_orderbook_stream(log=log, params=params)

    async def update_markets_info(self):
        """
            ccxt response:
            [{'active': True,
              'base': 'BTC',
              'baseId': 'BTC',
              'id': 'BTCUSD',
              'info': {'expiration': 'NA',
                       'initial_margin': '30.0',
                       'maximum_order_size': '2000.0',
                       'minimum_margin': '15.0',
                       'minimum_order_size': '0.002',
                       'pair': 'btcusd',
                       'price_precision': 5},
              'limits': {'amount': {'max': 2000.0, 'min': 0.002},
                         'cost': {'max': None, 'min': None},
                         'price': {'max': 100000.0, 'min': 1e-05}},
              'maker': 0.001,
              'percentage': True,
              'precision': {'amount': 5, 'price': 5},
              'quote': 'USD',
              'quoteId': 'USD',
              'symbol': 'BTC/USD',
              'taker': 0.002,
              'tierBased': True,
              'tiers': {'maker': [[0, 0.001],
                                  [500000, 0.0008],
                                  [1000000, 0.0006],
                                  [2500000, 0.0004],
                                  [5000000, 0.0002],
                                  [7500000, 0],
                                  [10000000, 0],
                                  [15000000, 0],
                                  [20000000, 0],
                                  [25000000, 0],
                                  [30000000, 0]],
                        'taker': [[0, 0.002],
                                  [500000, 0.002],
                                  [1000000, 0.002],
                                  [2500000, 0.002],
                                  [5000000, 0.002],
                                  [7500000, 0.002],
                                  [10000000, 0.0018],
                                  [15000000, 0.0016],
                                  [20000000, 0.0014000000000000002],
                                  [25000000, 0.0012],
                                  [30000000, 0.001]]}}
                ...
            ]
        """
        res = await self._send_ccxt_request(self.ex.fetch_markets)
        for mark in res:
            if mark['symbol'] in self.markets:
                self.markets_info[mark['symbol']] = mark
        return self.markets_info

