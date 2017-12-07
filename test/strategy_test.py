from setup import run, setup
setup()

import asyncio
from db import EXMongo
from strategy import BaseStrategy, PatternStrategy
from trader import SimulatedTrader
from utils import init_ccxt_exchange, exchange_timestamp

from pprint import pprint

timeframes = ['1m', '5m', '15m', '30m', '1h']
# timeframes = ['30m', '1h']

markets = ['BTC/USD', 'ETH/USD']

################################
#      TEST BASE STRATEGY      #
################################

async def test_feed_ohlcv(bs, mongo):
    exchange = init_ccxt_exchange('bitfinex2')

    start = exchange_timestamp(2017, 1, 1)
    end = exchange_timestamp(2017, 1, 2)

    ohlcvs = {}
    for tf in timeframes:
        ohlcvs[tf] = await mongo.get_ohlcv(exchange, 'BTC/USD', start, end, tf)

    for tf, ohlcv in ohlcvs.items():
        bs.feed_ohlcv(ohlcv, tf)

    pprint(bs.ohlcvs)


async def test_feed_trades(bs, mongo):
    exchange = init_ccxt_exchange('bitfinex2')

    start = exchange_timestamp(2017, 1, 1)
    end = exchange_timestamp(2017, 1, 2)

    fields_condition = {'symbol': 0}

    trades = await mongo.get_trades(exchange, 'BTC/USD', start, end, fields_condition=fields_condition)
    bs.feed_trades(trades)

    pprint(bs.trades)


async def test_base_strategy(mongo, trader):
    exchange = init_ccxt_exchange('bitfinex2')

    bs = BaseStrategy(trader, timeframes)
    await test_feed_ohlcv(bs, mongo)
    await test_feed_trades(bs, mongo)


################################
#     TEST PATTERN STRATEGY    #
################################

async def test_pattern_strategy(mongo, trader):
    ps = PatternStrategy(trader, markets, timeframes)
    pprint(ps.trades)

async def main():
    mongo = EXMongo()
    trader = SimulatedTrader()

    # Test BaseStrategy
    # await test_base_strategy(mongo, trader)

    # Test PatternStrategy
    await test_pattern_strategy(mongo, trader)





run(main)
