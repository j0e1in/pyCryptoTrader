from setup import run, setup
setup()

from pprint import pprint as pp
import ccxt.async as ccxt
import asyncio
import motor.motor_asyncio as motor
from asyncio import ensure_future
from datetime import datetime

from utils import combine, get_keys, get_constants, datetime_str, ms_sec
from hist_data import find_missing_candles

consts = get_constants()


async def main():
    mongo = motor.AsyncIOMotorClient('localhost', 27017)
    timeframe = '15m'
    coll_tamplate = "bitfinex_ohlcv_ETHUSD_{}"
    coll = getattr(mongo.exchange, coll_tamplate.format(timeframe))

    start_str = datetime_str(2017, 1, 1)
    end_str = datetime_str(2017, 11, 1)

    missing_candles_ts = await find_missing_candles(coll, start_str, end_str, timeframe)
    for ts in missing_candles_ts:
        print(datetime.utcfromtimestamp(ms_sec(ts)))

    print(len(missing_candles_ts))


run(main)
