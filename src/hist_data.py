from pprint import pprint as pp
import ccxt.async as ccxt
import asyncio
import logging
import time

from utils import get_constants, sec_ms

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
            print(start_timestamp)
            logger.info(f'Fetching {timeframe} candles starting from {exchange.iso8601(start_timestamp)}')
            ohlcvs = await exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=start_timestamp, params=params)
            logger.info(f'Fetched {len(ohlcvs)} candles')

            start_timestamp = ohlcvs[-1][0]
            del ohlcvs[-1]
            yield ohlcvs

        except (ccxt.ExchangeError, ccxt.AuthenticationError, ccxt.ExchangeNotAvailable, ccxt.RequestTimeout) as error:
            logger.info(f'|{type(error).__name__}| retrying in {wait} seconds...')
            await asyncio.sleep(wait)

