from setup import run, setup
setup()

import motor.motor_asyncio as motor

from db import EXMongo
from utils import ex_timestamp, init_ccxt_exchange
from hist_data import fill_missing_ohlcv

from pprint import pprint as pp


async def test_get_ohlcv(mongo):
    exchange = init_ccxt_exchange('bitfinex2')

    start = ex_timestamp(2017, 1, 1)
    end = ex_timestamp(2017, 1, 2)

    res = await mongo.get_ohlcv(exchange, 'BTC/USD', start, end, '1h')
    print('BTC/USD ohlcv')
    pp(res) # should not be empty

    res = await mongo.get_ohlcv(exchange, 'BCH/USD', start, end, '1h')
    print('BCH/USD ohlcv')
    pp(res) # should be empty


async def test_insert_ohlcv(mongo):
    exchange = init_ccxt_exchange('bitfinex2')
    symbol = 'ETH/USD'
    start = ex_timestamp(2017, 10, 1)
    end = ex_timestamp(2017, 11, 1)
    timeframe = '1m'

    filled_df = await fill_missing_ohlcv(
        mongo, exchange, symbol, start, end, timeframe)

    missing_ohlcv = filled_df[filled_df.volume == 0]

    print('#missing_ohlcv:', len(missing_ohlcv))
    await mongo.insert_ohlcv(missing_ohlcv, exchange, symbol, timeframe)


async def test_get_trades(mongo):
    exchange = init_ccxt_exchange('bitfinex2')

    start = ex_timestamp(2017, 1, 1)
    end = ex_timestamp(2017, 1, 2)
    res = await mongo.get_trades(exchange, 'BTC/USD', start, end)
    pp(res)


async def main():
    mongo = EXMongo()

    await test_get_ohlcv(mongo)
    await test_insert_ohlcv(mongo)
    await test_get_trades(mongo)


run(main)