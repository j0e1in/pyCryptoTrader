from setup import run, setup
setup()

import asyncio
from db import EXMongo
from strategy import BaseStrategy, PatternStrategy
from trader import SimulatedTrader
from utils import init_ccxt_exchange

from pprint import pprint

# timeframes = ['1m', '5m', '15m', '30m', '1h']
timeframes = ['30m', '1h']

markets = ['BTC/USD', 'ETH/USD']

################################
#      TEST BASE STRATEGY      #
################################

async def test_base_strategy(mongo, trader):
    exchange = init_ccxt_exchange('bitfinex2')
    bs = BaseStrategy(trader, markets, timeframes)

    # await test_feed_ohlcv(bs, mongo)
    # await test_feed_trades(bs, mongo)
    await test_feed_trades_speed(bs, mongo)


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
    # await test_pattern_strategy(mongo, trader)





run(main)
