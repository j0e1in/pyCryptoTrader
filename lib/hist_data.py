from pprint import pprint as pp
import ccxt.async as ccxt
from datetime import timedelta
import asyncio
import logging
import time

from utils import get_constants, sec_ms, timeframe_timedelta
from mongo import Mongo

logger = logging.getLogger()
log = logger.debug


async def fetch_ohlcv_handler(exchange, symbol, start_str, end_str, timeframe='1m'):
    """ Fetch all ohlcv candles since 'start_timestamp' and use generator to stream results. """
    start_timestamp = exchange.parse8601(start_str)
    end_timestamp = exchange.parse8601(end_str)
    now = sec_ms(time.time())
    wait = get_constants()['wait']
    params = {
        'end': end_timestamp,
        'sort': 1
    }

    while start_timestamp < end_timestamp:

        try:
            logger.info(f'Fetching {timeframe} candles starting from {exchange.iso8601(start_timestamp)}')
            ohlcvs = await exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=start_timestamp, params=params)
            start_timestamp = ohlcvs[-1][0]
            del ohlcvs[-1]
            yield ohlcvs

        except (ccxt.ExchangeError, ccxt.AuthenticationError, ccxt.ExchangeNotAvailable, ccxt.RequestTimeout) as error:
            logger.info(f'|{type(error).__name__}| retrying in {wait} seconds...')
            await asyncio.sleep(wait)


async def find_missing_candles(coll, timeframe):

    if not Mongo.check_colums(coll, ['timestamp', 'open', 'close', 'high', 'low', 'volume']):
        raise ValueError('Collection\'s colums do not match candles.')

    td = timeframe_timedelta(timeframe)
    td = sec_ms(td.seconds)
    ts = prev_ts = None
    missing_candles = []

    async for candle in coll.find():
        ts = candle['timestamp']
        if prev_ts and ts:
            while prev_ts+td <= ts:
                if prev_ts+td != ts:
                    missing_candles.append(prev_ts+td)
                    prev_ts += td
                    ## TODO ##

    return missing_candles


async def remove_dup_candles(coll, timeframe):
    remove_count = 0
    ## TODO ##
    return remove_count
