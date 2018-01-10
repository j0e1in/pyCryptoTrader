from setup import run, setup
setup()

from datetime import datetime
from pprint import pprint

from analysis.backtest import ParamOptimizer
from analysis.strategy import PatternStrategy
from db import EXMongo


def print_num_tests(optimizer):
    ll = 1
    for k, v in optimizer.param_q.items():
        print('len', len(v))
        l = len(v)
        ll *= l
    print('total', ll)
    print()


## Defualt values
# "wvf_conf": 50,
# "wvf_lbsdh": 22,
# "wvf_bbl": 20,
# "wvf_bbsd": 2.0,
# "wvf_lbph": 50,
# "wvf_ph": 0.85,
# "wvf_ltLB": 40,
# "wvf_mtLB": 14,
# "wvf_strg": 3

async def find_optimal_paramters(mongo):
    periods = []

    # Test each month seperately
    # for i in range(1, 3):
    #     periods.append((datetime(2017, i, 1), datetime(2017, i+1, 1)))

    # Test all-time
    periods = [(datetime(2017, 1, 1), datetime(2017, 11, 1))]

    strategy = PatternStrategy('bitfinex')
    optimizer = ParamOptimizer(mongo, strategy, periods)

    optimizer.optimize_selection('wvf_tf', ['30m', '1h'])
    optimizer.optimize_range('trade_portion', 0.4, 1, 0.2)
    optimizer.optimize_range('wvf_conf', 30, 80, 20)
    optimizer.optimize_range('wvf_lbsdh', 10, 40, 15)
    optimizer.optimize_range('wvf_bbl', 1, 40, 20)
    optimizer.optimize_range('wvf_bbsd', 1, 5, 2)
    optimizer.optimize_range('wvf_lbph', 30, 80, 20)
    optimizer.optimize_range('wvf_ph', 0.5, 1, 0.2)

    optimizer.optimize_range('wvf_ltLB', 30, 80, 25)
    optimizer.optimize_range('wvf_mtLB', 7, 20, 6)
    optimizer.optimize_range('wvf_strg', 1, 10, 5)

    print_num_tests(optimizer)

    summaries = await optimizer.run()
    summary = optimizer.analyze_summary(summaries, 'best_params')
    summary.to_csv('../data/opt.csv')


async def main():
    mongo = EXMongo()

    await find_optimal_paramters(mongo)


if __name__ == '__main__':
    run(main)


