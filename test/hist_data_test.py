from test import run_test, setup
setup()

from pprint import pprint as pp
from datetime import datetime
import ccxt.async as ccxt
import asyncio
import logging
import time

from utils import combine, get_keys, get_constants, datetime_str, ms_sec
from hist_data import fetch_ohlcv_handler

consts = get_constants()


async def main():

    options = combine({
        'rateLimit': consts['rate_limit'],
        'enableRateLimit': True
    }, get_keys()['bitfinex'])

    start_str = datetime_str(2017, 10, 1)
    end_str = datetime_str(2017, 10, 2)

    exchange = ccxt.bitfinex2(options)
    await exchange.load_markets()

    res = fetch_ohlcv_handler(exchange, 'BTC/USD', start_str, end_str, '1m')
    async for r in res:
        for candle in r:
            print(datetime.utcfromtimestamp(ms_sec(candle[0])))



run_test(main)
