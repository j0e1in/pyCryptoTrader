from setup import run, setup
setup()

from datetime import datetime

import motor.motor_asyncio as motor

from db import EXMongo
from utils import init_ccxt_exchange
from hist_data import fill_missing_ohlcv

from pprint import pprint as pp


async def test_get_ohlcv(mongo):
    exchange = init_ccxt_exchange('bitfinex2')

    start = datetime(2017, 1, 1)
    end = datetime(2017, 1, 2)

    res = await mongo.get_ohlcv(exchange, 'BTC/USD', '1h', start, end)
    print('BTC/USD ohlcv')
    pp(res)  # should not be empty

    res = await mongo.get_ohlcv(exchange, 'BCH/USD', '1h', start, end)
    print('BCH/USD ohlcv')
    pp(res)  # should be empty


async def test_get_trades(mongo):
    exchange = init_ccxt_exchange('bitfinex2')

    start = datetime(2017, 1, 1)
    end = datetime(2017, 1, 2)
    res = await mongo.get_trades(exchange, 'BTC/USD', start, end)
    pp(res)


async def test_insert_ohlcv(mongo):
    exchange = init_ccxt_exchange('bitfinex2')
    symbol = 'ETH/USD'
    start = datetime(2017, 10, 1)
    end = datetime(2017, 11, 1)
    timeframe = '1m'

    filled_df = await fill_missing_ohlcv(
        mongo, exchange, symbol, start, end, timeframe)

    missing_ohlcv = filled_df[filled_df.volume == 0]

    print(missing_ohlcv)

    print('number of missing ohlcv:', len(missing_ohlcv))
    await mongo.insert_ohlcv(missing_ohlcv, exchange, symbol, timeframe, coll_prefix="test_")


async def main():
    mongo = EXMongo()

    print('------------------------------')
    await test_get_ohlcv(mongo)
    print('------------------------------')
    await test_get_trades(mongo)
    print('------------------------------')
    await test_insert_ohlcv(mongo)
    print('------------------------------')


if __name__ == '__main__':
    run(main)
