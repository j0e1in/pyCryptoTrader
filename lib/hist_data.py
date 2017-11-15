from pprint import pprint as pp
import ccxt.async as ccxt
from ccxt.base.exchange import Exchange
from datetime import timedelta
import asyncio
import logging
import time

from utils import get_constants, sec_ms, ms_sec, timeframe_timedelta, utcms_dt
from mongo import Mongo

logger = logging.getLogger()
log = logger.debug


async def fetch_ohlcv_handler(exchange, symbol, start, end, timeframe='1m'):
    """ Fetch all ohlcv candles since 'start_timestamp' and use generator to stream results. """
    now = sec_ms(time.time())
    wait = get_constants()['wait']
    params = {
        'end': end,
        'sort': 1
    }

    while start < end:
        try:
            logger.info(f'Fetching {symbol}_{timeframe} candles starting from {utcms_dt(start)}')
            ohlcvs = await exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=start, params=params)
            start = ohlcvs[-1][0]
            del ohlcvs[-1]
            yield ohlcvs

        except (ccxt.ExchangeError,
                ccxt.AuthenticationError,
                ccxt.ExchangeNotAvailable,
                ccxt.RequestTimeout,
                ccxt.DDoSProtection) as error:
            logger.info(f'|{type(error).__name__}| retrying in {wait} seconds...')
            await asyncio.sleep(wait)


async def find_missing_candles(coll, start, end, timeframe):

    if not Mongo.check_colums(coll, ['timestamp', 'open', 'close', 'high', 'low', 'volume']):
        raise ValueError('Collection\'s colums do not match candle\'s.')

    td = timeframe_timedelta(timeframe)
    td = sec_ms(td.seconds)

    prev_ts = start - td
    ts = None

    res = coll.find({'timestamp': {'$gte': start, '$lt': end}}).sort('timestamp', 1)

    missing_candles = []
    async for candle in res:
        ts = candle['timestamp']
        while prev_ts+td <= ts:
            if prev_ts+td != ts:
                missing_candles.append(prev_ts+td)
            prev_ts += td

    return missing_candles


async def fetch_trades_handler(exchange, symbol, start, end):

    def remove_last_timestamp(records):
        _last_timestamp = records[-1]['timestamp']
        ts = ms_sec(_last_timestamp)

        i = -1
        for _ in range(1, len(records)-1):
            if ms_sec(records[i]['timestamp']) == ts:
                del records[i]
            else:
                break

        return _last_timestamp, records


    now = sec_ms(time.time())
    wait = get_constants()['wait']
    params = {
        'start': start,
        'end': end,
        'limit': 1000,
        'sort': 1
    }

    while start < end:
        try:
            logger.info(f'Fetching {symbol} trades starting from {utcms_dt(start)}')
            trades = await exchange.fetch_trades(symbol, params=params)
            if trades[0]['timestamp'] == trades[-1]['timestamp']:
                # All 1000 trades have the same timestamp, (unlikely to happen)
                # just ignore the rest of trades that have same timestamp,
                # no much we can do about it.
                start += 1000
            else:
                start, trades = remove_last_timestamp(trades)
            params['start'] = start
            yield trades

        except (ccxt.ExchangeError,
                ccxt.AuthenticationError,
                ccxt.ExchangeNotAvailable,
                ccxt.RequestTimeout,
                ccxt.DDoSProtection) as error:
            logger.info(f'|{type(error).__name__}| retrying in {wait} seconds...')
            await asyncio.sleep(wait)

