from setup import run, setup
setup()

import asyncio
import matplotlib.pyplot as plt
from datetime import datetime
from pprint import pprint

from backtest import Backtest
from db import EXMongo
from strategy import PatternStrategy




################################
#     TEST PATTERN STRATEGY    #
################################

async def test_pattern_strategy(mongo):
    start = datetime(2017, 6, 1)
    end = datetime(2017, 6, 15)
    exchange = 'bitfinex'
    strategy = PatternStrategy(exchange)

    options = {
        'strategy': strategy,
        'start': start,
        'end': end
    }
    backtest = await Backtest(mongo).init(**options)
    report = backtest.run()

    pprint(backtest.trader.order_history)

    print('\n-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=\n')
    pprint(report)
    print('\n-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=\n')


async def main():
    mongo = EXMongo()

    await test_pattern_strategy(mongo)


if __name__ == '__main__':
    run(main)