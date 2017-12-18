from setup import run, setup
setup()

from datetime import datetime
import asyncio

from backtest import Backtest
from db import EXMongo
from strategy import SingleExchangeStrategy, PatternStrategy
from trader import SimulatedTrader
from utils import Timer, config

from pprint import pprint


################################
#     TEST PATTERN STRATEGY    #
################################

async def test_pattern_strategy(mongo):
    start = datetime(2017, 9, 1)
    end = datetime(2017, 9, 10)
    exchange = 'bitfinex'
    strategy = PatternStrategy(exchange)

    options = {
        'strategy': strategy,
        'start': start,
        'end': end
    }
    backtest = await Backtest(mongo).init(options)
    report = backtest.run()

    pprint(report)


async def main():
    mongo = EXMongo()

    # Test SingleExchangeStrategy
    # await test_base_strategy(mongo)

    # Test PatternStrategy
    await test_pattern_strategy(mongo)





run(main)
