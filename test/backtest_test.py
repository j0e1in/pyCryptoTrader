from setup import run, setup
setup()

from datetime import datetime
from pprint import pprint

from backtest import Backtest, BacktestRunner, ParamOptimizer
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


async def test_backtest_runner_run_fix_periods(mongo):
    periods = []

    for i in range(10):
        periods.append((datetime(2017, 3, i+1), datetime(2017, 4, i+1)))

    strategy = PatternStrategy('bitfinex')
    bt_runner = BacktestRunner(mongo, strategy)

    summary = await bt_runner.run_periods(periods)
    pprint(summary)


async def test_backtest_runner_run_random_periods(mongo):
    start = datetime(2017, 1, 1)
    end = datetime(2017, 3, 1)
    period_size_range = (15, 29)

    strategy = PatternStrategy('bitfinex')
    bt_runner = BacktestRunner(mongo, strategy)

    periods = bt_runner.generate_random_periods(start, end, period_size_range, 15)
    summary = await bt_runner.run_periods(periods)
    pprint(summary)


async def test_backtest_runner_run_period_with_shift_step(mongo):
    start = datetime(2017, 3, 1)
    end = datetime(2017, 5, 31)
    period_size = 30
    shift_step = 5

    strategy = PatternStrategy('bitfinex')
    bt_runner = BacktestRunner(mongo, strategy)

    periods = bt_runner.generate_periods_with_shift_step(start, end, period_size, shift_step)
    summary = await bt_runner.run_periods(periods)
    pprint(summary)


async def test_param_optimizer(mongo):
    periods = []
    for i in range(2):
        periods.append((datetime(2017, 3, i+1), datetime(2017, 3, i+15)))

    strategy = PatternStrategy('bitfinex')
    optimizer = ParamOptimizer(mongo, strategy, periods)

    optimizer.optimize_range('trade_portion', 0.1, 0.2, 0.1)
    optimizer.optimize_selection('wvf_tf', ['30m', '1h'])
    summaries = await optimizer.run()
    summary = optimizer.analyze_summary(summaries, 'best_params')
    print(summary)


async def main():
    mongo = EXMongo()
    backtest = Backtest(mongo)

    print('------------------------------')
    await test_run(backtest)
    print('------------------------------')
    await test_backtest_runner_run_fix_periods(mongo)
    print('------------------------------')
    await test_backtest_runner_run_random_periods(mongo)
    print('------------------------------')
    await test_backtest_runner_run_period_with_shift_step(mongo)
    print('------------------------------')
    await test_param_optimizer(mongo)

if __name__ == '__main__':
    run(main)
