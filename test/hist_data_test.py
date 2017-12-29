from setup import run, setup
setup()

from datetime import datetime
import motor.motor_asyncio as motor
import pandas as pd

from db import EXMongo
from utils import ms_sec, init_ccxt_exchange, ms_dt
from hist_data import fetch_ohlcv, \
                      fetch_trades, \
                      find_missing_ohlcv, \
                      fill_missing_ohlcv


async def test_fetch_ohlcv():
    exchange = init_ccxt_exchange('bitfinex2')

    start = datetime(2017, 10, 1)
    end = datetime(2017, 10, 2)

    ohlcv = fetch_ohlcv(exchange, 'ETH/USD', start, end, timeframe='5m')
    async for oh in ohlcv:
        print('Last ohlcv:', ms_dt(oh[-1][0]))


async def test_fetch_trades():
    exchange = init_ccxt_exchange('bitfinex2')

    start = datetime(2017, 10, 1)
    end = datetime(2017, 10, 1, 1)

    trades = fetch_trades(exchange, 'ETH/USD', start, end)
    async for trd in trades:
        print('Last trade:', ms_dt(trd[-1]['timestamp']))


async def test_find_missing_ohlcv():
    mongo = motor.AsyncIOMotorClient('localhost', 27017)

    timeframe = '15m'
    coll_tamplate = "bitfinex_ohlcv_ETHUSD_{}"
    coll = getattr(mongo.exchange, coll_tamplate.format(timeframe))

    start = datetime(2017, 10, 1)
    end = datetime(2017, 11, 1)

    count = 0
    missing_ohlcv_ts = await find_missing_ohlcv(coll, start, end, timeframe)
    for ts in missing_ohlcv_ts:
        count += 1
        print("Missing: ", ts, '-', datetime.utcfromtimestamp(ms_sec(ts)))

    print("Total missing ohlcv:", count)


async def test_fill_ohlcv_missing_timestamp():
    mongo = EXMongo()
    exchange = init_ccxt_exchange('bitfinex2')
    symbol = 'ETH/USD'
    timeframe = '15m'

    start = datetime(2017, 10, 1)
    end = datetime(2017, 11, 1)

    filled_df = await fill_missing_ohlcv(
        mongo, exchange, symbol, start, end, timeframe)

    missing_ohlcv = filled_df[filled_df.volume == 0]
    print('#missing_ohlcv', len(missing_ohlcv))


async def main():
    print('-----------------------------')
    await test_fetch_ohlcv()
    print('-----------------------------')
    await test_fetch_trades()
    print('-----------------------------')
    await test_find_missing_ohlcv()
    print('-----------------------------')
    await test_fill_ohlcv_missing_timestamp()


if __name__ == '__main__':
    run(main)

