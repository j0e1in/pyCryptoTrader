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
    options = {
        'strategy': PatternStrategy('bitfinex'),
        'start': datetime(2017, 1, 2),
        'end': datetime(2017, 1, 17)
    }

    backtest = await Backtest(mongo).init(**options)
    report = backtest.run()

    # pprint(backtest.trader.order_history)
    backtest.plot.show()

    print('\n-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=\n')
    pprint(report)
    print('\n-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=\n')


async def main():
    mongo = EXMongo()

    await test_pattern_strategy(mongo)


if __name__ == '__main__':
    run(main)