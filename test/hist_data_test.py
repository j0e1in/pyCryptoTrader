from setup import run, setup
setup()

import motor.motor_asyncio as motor
from datetime import datetime

from utils import get_constants, exchange_timestamp, ms_sec
from hist_data import find_missing_candles


async def test_find_missing_candles()
    mongo = motor.AsyncIOMotorClient('localhost', 27017)
    timeframe = '15m'
    coll_tamplate = "bitfinex_ohlcv_ETHUSD_{}"
    coll = getattr(mongo.exchange, coll_tamplate.format(timeframe))

    start = exchange_timestamp(2017, 1, 1)
    end = exchange_timestamp(2017, 11, 1)

    missing_candles_ts = await find_missing_candles(coll, start, end, timeframe)
    for ts in missing_candles_ts:
        print(datetime.utcfromtimestamp(ms_sec(ts)))


async def test_fetch_trades_handler():
    pass


async def main():
    # await test_find_missing_candles()

    await test_fetch_trades_handler()


run(main)
