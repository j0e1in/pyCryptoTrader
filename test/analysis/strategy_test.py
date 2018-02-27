from setup import run, setup
setup()

from datetime import datetime
from pprint import pprint

from analysis.backtest import Backtest
from analysis.strategy import PatternStrategy
from db import EXMongo




################################
#     TEST PATTERN STRATEGY    #
################################

async def test_pattern_strategy(mongo):
    options = {
        'strategy': PatternStrategy('bitfinex'),
        'start': datetime(2017, 4, 2),
        'end': datetime(2017, 4, 17)
    }

    backtest = await Backtest(mongo).init(**options)
    report = backtest.run()

    print('\n-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=\n')
    pprint(report)
    print('\n-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=\n')


async def main():
    mongo = EXMongo()

    await test_pattern_strategy(mongo)


if __name__ == '__main__':
    run(main)