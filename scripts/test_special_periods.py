from setup import run, setup
setup()

import pickle
from datetime import datetime
from pprint import pprint

from backtest import Backtest, BacktestRunner
from db import EXMongo
from strategy import PatternStrategy


async def test_single_period(mongo):
    dt = (datetime(2017, 3, 17), datetime(2017, 3, 19))

    options = {
        'strategy': PatternStrategy('bitfinex'),
        'start': dt[0],
        'end': dt[1]
    }

    backtest = await Backtest(mongo).init(**options)
    report = backtest.run()
    backtest.plot.show()

    print('\n-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=\n')
    pprint(report)
    print('\n-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=\n')


async def test_special_periods(mongo):
    periods = [
        (datetime(2017, 3, 17), datetime(2017, 3, 19)),
        (datetime(2017, 3, 25), datetime(2017, 4, 26)),
        (datetime(2017, 5, 15), datetime(2017, 5, 26)),
        (datetime(2017, 5, 28), datetime(2017, 6, 14)),
        (datetime(2017, 6, 7), datetime(2017, 6, 28)),
        (datetime(2017, 6, 18), datetime(2017, 6, 27, 14)),
        (datetime(2017, 9, 2), datetime(2017, 9, 15, 11)),
    ]

    strategy = PatternStrategy('bitfinex')
    bt_runner = BacktestRunner(mongo, strategy)

    summary = await bt_runner.run_periods(periods)
    pprint(summary)


async def test_random_periods(mongo):
    filename = 'DASH_random_1'

    start = datetime(2017, 3, 5)
    end = datetime(2017, 11, 1)
    period_size_range = (7, 100)

    strategy = PatternStrategy('bitfinex')
    bt_runner = BacktestRunner(mongo, strategy)

    periods = bt_runner.generate_random_periods(start, end, period_size_range, 2000)

    with open(f'../data/{filename}.pkl', 'wb') as f:
        pickle.dump(periods, f)

    pprint(periods)

    summary = await bt_runner.run_periods(periods)
    summary.to_csv(f'../data/{filename}.csv')


async def main():
    mongo = EXMongo()

    await test_single_period(mongo)
    await test_special_periods(mongo)
    await test_random_periods(mongo)


if __name__ == '__main__':
    run(main)
