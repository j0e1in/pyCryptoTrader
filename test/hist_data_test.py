from setup import run, setup
setup()

import motor.motor_asyncio as motor
from datetime import datetime
import pandas as pd

from db import EXMongo
from utils import utc_ts, ms_sec, init_ccxt_exchange, ms_dt
from hist_data import find_missing_ohlcv, \
                      fetch_trades_handler, \
                      fill_missing_ohlcv


async def test_find_missing_ohlcv():
    mongo = motor.AsyncIOMotorClient('localhost', 27017)

    timeframe = '15m'
    coll_tamplate = "bitfinex_ohlcv_ETHUSD_{}"
    coll = getattr(mongo.exchange, coll_tamplate.format(timeframe))

    start = utc_ts(2017, 1, 1)
    end = utc_ts(2017, 11, 1)

    count = 0
    missing_ohlcv_ts = await find_missing_ohlcv(coll, start, end, timeframe)
    for ts in missing_ohlcv_ts:
        count += 1
        # print(ts, '-', datetime.utcfromtimestamp(ms_sec(ts)))

    print("Total missing ohlcv:", count)


async def test_fetch_trades_handler():
    exchange = init_ccxt_exchange('bitfinex2')

    start = utc_ts(2017, 10, 1)
    end = utc_ts(2017, 11, 1)

    trades = fetch_trades_handler(exchange, 'ETH/USD', start, end)
    async for trd in trades:
        print('Last trade:', ms_dt(trd[-1]['timestamp']))


async def test_fill_ohlcv_missing_timestamp():
    mongo = EXMongo()
    exchange = init_ccxt_exchange('bitfinex2')
    symbol = 'ETH/USD'
    start = utc_ts(2017, 10, 1)
    end = utc_ts(2017, 11, 1)
    timeframe = '15m'

    filled_df = await fill_missing_ohlcv(
        mongo, exchange, symbol, start, end, timeframe)

    missing_ohlcv = filled_df[filled_df.volume == 0]
    print('#missing_ohlcv', len(missing_ohlcv))


async def main():
    # await test_find_missing_ohlcv()
    # await test_fetch_trades_handler()
    await test_fill_ohlcv_missing_timestamp()

run(main)
