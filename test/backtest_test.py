from setup import run, setup
setup()

from datetime import datetime
from pprint import pprint

from backtest import Backtest
from db import EXMongo
from strategy import SingleExchangeStrategy


async def test_run(backtest):
    # Add `"BTC": 1` to config['trader']['funds'] to test thoroughly.

    strategy = SingleExchangeStrategy('bitfinex')
    start = datetime(2017, 1, 1)
    end = datetime(2017, 3, 1)
    options = {
        'strategy': strategy,
        'start': start,
        'end': end
    }
    await backtest.init(options)
    report = backtest.run()
    pprint(report)


async def main():
    mongo = EXMongo()
    backtest = Backtest(mongo)

    print('------------------------------')
    await test_run(backtest)


run(main)