from setup import run


from datetime import datetime

import motor.motor_asyncio as motor

from analysis.hist_data import fill_missing_ohlcv
from db import EXMongo, Datastore
from utils import init_ccxt_exchange, config

from pprint import pprint as pp


async def test_get_ohlcv(mongo):
    exchange = init_ccxt_exchange('bitfinex2')

    start = datetime(2017, 4, 1)
    end = datetime(2017, 4, 2)

    res = await mongo.get_ohlcv(exchange, 'BTC/USD', '1h', start, end)
    print('BTC/USD ohlcv')
    pp(res)  # should not be empty

    res = await mongo.get_ohlcv(exchange, 'BCH/USD', '1h', start, end)
    print('BCH/USD ohlcv')
    pp(res)  # should be empty


async def test_get_trades(mongo):
    exchange = init_ccxt_exchange('bitfinex2')

    start = datetime(2017, 4, 1)
    end = datetime(2017, 4, 2)
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


async def test_get_ohlcv_trade_start_end(mongo):
    sym = config['trading']['bitfinex']['markets'][0]
    tf = config['trading']['bitfinex']['timeframes'][0]

    print("ohlcv start:", await mongo.get_ohlcv_start('bitfinex', sym, tf))
    print("ohlcv end:", await mongo.get_ohlcv_end('bitfinex', sym, tf))
    print("trades start:", await mongo.get_trades_start('bitfinex', sym))
    print("trades end:", await mongo.get_trades_end('bitfinex', sym))


def test_datastore():
    datastore = Datastore.create('delta')
    datastore.ds = datastore
    assert datastore.ds == datastore

    dd = {'key': 'value'}
    datastore.alpha = dd
    assert datastore.alpha == dd

    print(datastore['alpha'])
    print('keys:', datastore.keys())
    print('dir: ', dir(datastore))
    print('dict:', dict(datastore))
    print('list:', list(datastore))
    print('len: ', len(datastore))
    print('get: ', datastore.get('none', 'default'))


def test_datastore_sync():
    datastore = Datastore.create('delta2')

    dd = Datastore.create('tmp')
    dd.attr = [1, 2, 3]
    dd.attr2 = [4, 5, 6]
    datastore.attr = dd.attr
    datastore.attr2 = dd.attr2
    assert dd.attr == [1, 2, 3]
    assert dd.attr2 == [4, 5, 6]

    dd.attr = [7, 7, 7]
    dd.attr2 = [8, 8, 8]

    ds_list = ['attr', 'attr2']
    datastore.sync(ds_list, dd)
    assert dd.attr == [7, 7, 7]
    assert dd.attr2 == [8, 8, 8]


async def main():
    mongo = EXMongo()

    # print('------------------------------')
    # await test_get_ohlcv(mongo)
    # print('------------------------------')
    # await test_get_trades(mongo)
    # print('------------------------------')
    # await test_insert_ohlcv(mongo)
    # print('------------------------------')
    # await test_get_ohlcv_trade_start_end(mongo)
    print('------------------------------')
    test_datastore()
    print('------------------------------')
    test_datastore_sync()


if __name__ == '__main__':
    run(main)
