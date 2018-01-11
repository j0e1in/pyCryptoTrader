from pprint import pprint
from asyncio import ensure_future
from pymongo.errors import BulkWriteError
import asyncio
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
    rsym

from ipdb import set_trace as trace


logger = logging.getLogger()


class EX():
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

        self.streams_ready = {}

    def isauth(self):
        return True if self.apikey and self.secret else False

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

    def is_ready(self):
        """ Return True if data streams are up-to-date. """
        for _, ready in self.streams_ready.items():
            if not ready:
                return False
        return True

    async def start(self, data_streams=['ohlcv']):
        """ Start data streams and load account data.
            Trader can only use EX instance if it's started and ready.
        """
        streams = []
        if 'ohlcv' in data_streams:
            streams.append(ensure_future(self._start_ohlcv_stream()))
            self.streams_ready['ohlcv'] = False

        if 'trade' in data_streams:
            streams.append(self._start_trade_stream())
            self.streams_ready['trade'] = False

        if 'ticker' in data_streams:
            streams.append(self._start_ticker_stream())
            self.streams_ready['ticker'] = False

        if 'orderbook' in data_streams:
            streams.append(self._start_orderbook_stream())
            self.streams_ready['orderbook'] = False

        await asyncio.gather(*streams)

    async def _start_ohlcv_stream(self):

        async def fetch_ohlcv_to_mongo(symbol, start, end, timeframe):
            ops = []
            count = 0

            collname = f"{self.exname}_ohlcv_{rsym(symbol)}_{timeframe}"
            coll = self.mongo.get_collection('exchange', collname)
            res = fetch_ohlcv(self.ex, symbol, start, end, timeframe)

            async for ohlcv in res:
                processed_ohlcv = []

                logger.debug(f'Fetched {len(ohlcv)} ohlcvs')

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
        tasks = []

        while True:
            await self.update_ohlcv_start_end()

            for market in self.markets:
                for tf in self.timeframes:

                    td = timeframe_timedelta(tf)
                    cur_time = rounddown_dt(utc_now(), sec=td.seconds)
                    end = self.ohlcv_start_end[market][tf][1]

                    if end < cur_time:
                        ready = False
                        tasks.append(ensure_future(fetch_ohlcv_to_mongo(market, end, cur_time, tf)))

            await asyncio.gather(*tasks)

            if await is_uptodate(self.ohlcv_start_end):
                self.streams_ready['ohlcv'] = True
                await asyncio.sleep(self.config['data_delay_tolerence']/8)

    async def _start_trade_stream(self):
        pass

    async def _start_ticker_stream(self):
        pass

    async def _start_orderbook_stream(self):
        pass

    @staticmethod
    async def _exec_mongo_op(func, *args, **kwargs):
        try:
            await func(*args, **kwargs)
        except BulkWriteError as err:
            for msg in err.details['writeErrors']:
                if 'duplicate' in msg['errmsg']:
                    continue
                else:
                    pprint(err.details)
                    raise BulkWriteError(err)

    async def update_ohlcv_start_end(self):
        # Get available ohlcv start / end datetime in db
        self.ohlcv_start_end = {}
        for market in self.markets:
            self.ohlcv_start_end[market] = {}

            for tf in self.timeframes:
                start = await self.mongo.get_ohlcv_start(self.exname, market, tf)
                end = await self.mongo.get_ohlcv_end(self.exname, market, tf)
                self.ohlcv_start_end[market][tf] = (start, end)

    #####################
    # AUTHENTICATED API #
    #####################

    async def _send_ccxt_request(self, func, *args, **kwargs):
        succ = False
        count = 0

        while not succ:
            if count > self.config['max_retry']:
                logger.error(f"{func} exceeds max retries")
                return None

            count += 1
            try:
                res = await func(*args, **kwargs)

            except (ccxt.RequestTimeout,
                    ccxt.DDoSProtection) as error:

                if is_empty_response(error):  # finished fetching all ohlcv
                    break
                elif isinstance(error, ccxt.ExchangeError):
                    raise error

                logger.info(f'|{type(error).__name__}| retrying in {wait} seconds...')
                await asyncio.sleep(wait)

            else:
                succ = True

        return res


def is_empty_response(err):
    return True if 'empty response' in str(err) else False
