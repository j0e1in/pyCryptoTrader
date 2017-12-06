from setup import run, setup
setup()

import asyncio
from db import EXMongo
from strategy import BaseStrategy
from utils import init_exchange, exchange_timestamp

from pprint import pprint

ohlcv_timeframes = ['1m', '5m', '15m', '30m', '1h']
# ohlcv_timeframes = ['30m', '1h']

async def test_feed_ohlcv(mongo):
    bs = BaseStrategy(ohlcv_timeframes)

    exchange = init_exchange('bitfinex2')
    start = exchange_timestamp(2017, 1, 1)
    end = exchange_timestamp(2017, 1, 2)

    ohlcvs = {}
    for tf in ohlcv_timeframes:
        ohlcvs[tf] = await mongo.get_ohlcv(exchange, 'BTC/USD', start, end, tf)

    for tf, ohlcv in ohlcvs.items():
        bs.feed_ohlcv(ohlcv, tf)

    pprint(bs.ohlcvs)


async def test_feed_trades(mongo):
    bs = BaseStrategy(ohlcv_timeframes)

    exchange = init_exchange('bitfinex2')
    start = exchange_timestamp(2017, 1, 1)
    end = exchange_timestamp(2017, 1, 2)

    fields_condition = {'symbol': 0}

    trades = await mongo.get_trades(exchange, 'BTC/USD', start, end, fields_condition=fields_condition)
    bs.feed_trades(trades)

    pprint(bs.trades)


async def main():
    mongo = EXMongo()

    # await test_feed_ohlcv(mongo)
    await test_feed_trades(mongo)


run(main)
