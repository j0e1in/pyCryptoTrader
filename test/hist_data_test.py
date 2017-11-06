from setup import run, setup
setup()

from pprint import pprint as pp
import ccxt.async as ccxt
import asyncio
import motor.motor_asyncio as motor
from asyncio import ensure_future
from datetime import datetime

from utils import combine, get_keys, get_constants, datetime_str, ms_sec
from hist_data import find_missing_candles, remove_dup_candles

consts = get_constants()


async def main():
    mongo = motor.AsyncIOMotorClient('localhost', 27017)
    coll = mongo.exchange.bitfinex_ohlcv_5m

    start_str = datetime_str(2017, 1, 1)
    end_str = datetime_str(2017, 11, 1)

    for ts in await find_missing_candles(coll, start_str, end_str, '5m'):
        print(datetime.utcfromtimestamp(ms_sec(ts)))


run(main)
