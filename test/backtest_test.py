from setup import run, setup
setup()

from datetime import datetime
from pprint import pprint

from backtest import Backtest, BacktestRunner
from db import EXMongo
from strategy import SingleExchangeStrategy, PatternStrategy


async def test_run(backtest):
    # Add `"BTC": 1` to config['trader']['funds'] to test thoroughly.

    strategy = SingleExchangeStrategy('bitfinex')
    start = datetime(2017, 1, 1)
    end = datetime(2017, 2, 5)
    options = {
        'strategy': strategy,
        'start': start,
        'end': end
    }
    await backtest.init(**options)
    report = backtest.run()
    pprint(report)


async def test_backtest_runner_run_fix_periods():
    periods = [
        (datetime(2017, 1, 2), datetime(2017, 1, 7)),
        (datetime(2017, 1, 2), datetime(2017, 1, 9))
    ]

    strategy = PatternStrategy('bitfinex')
    bt_runner = BacktestRunner(strategy)

    summary = await bt_runner.run_fixed_periods(periods)
    pprint(summary)


async def test_backtest_runner_run_random_periods():
    start = datetime(2017, 1, 1)
    end = datetime(2017, 3, 1)
    period_size_range = (20, 29)

    strategy = PatternStrategy('bitfinex')
    bt_runner = BacktestRunner(strategy)

    summary = await bt_runner.run_random_periods(start, end, period_size_range, 5)
    pprint(summary)


async def test_backtest_runner_run_period_with_shift_step():
    start = datetime(2017, 1, 1)
    end = datetime(2017, 3, 1)
    period_size = 15
    shift_step = 10

    strategy = PatternStrategy('bitfinex')
    bt_runner = BacktestRunner(strategy)

    summary = await bt_runner.run_period_with_shift_step(start, end, period_size, shift_step)
    pprint(summary)



async def main():
    mongo = EXMongo()
    backtest = Backtest(mongo)

    print('------------------------------')
    await test_run(backtest)
    print('------------------------------')
    await test_backtest_runner_run_fix_periods()
    print('------------------------------')
    await test_backtest_runner_run_random_periods()
    print('------------------------------')
    await test_backtest_runner_run_period_with_shift_step()


if __name__ == '__main__':
    run(main)
