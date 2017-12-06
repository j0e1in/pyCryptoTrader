from setup import run, setup
setup()

import motor.motor_asyncio as motor

from db import EXMongo
from utils import exchange_timestamp, init_exchange
from hist_data import fill_missing_ohlcv

from pprint import pprint as pp


async def test_get_ohlcv():
    exchange = init_exchange('bitfinex2')
    mongo = EXMongo()

    start = exchange_timestamp(2017, 1, 1)
    end = exchange_timestamp(2017, 1, 2)
    res = await mongo.get_ohlcv(exchange, 'BTC/USD', start, end, '1h')
    pp(res)
    res = await mongo.get_ohlcv(exchange, 'BCH/USD', start, end, '1h')
    pp(res)


async def test_insert_ohlcv():
    mongo = EXMongo()
    exchange = init_exchange('bitfinex2')
    symbol = 'ETH/USD'
    start = exchange_timestamp(2017, 10, 1)
    end = exchange_timestamp(2017, 11, 1)
    timeframe = '1m'

    filled_df = await fill_missing_ohlcv(
        mongo, exchange, symbol, start, end, timeframe)

    missing_ohlcv = filled_df[filled_df.volume == 0]

    print('#missing_ohlcv:', len(missing_ohlcv))
    await mongo.insert_ohlcv(missing_ohlcv, exchange, symbol, timeframe)


async def main():
    await test_get_ohlcv()
    await test_insert_ohlcv()


run(main)