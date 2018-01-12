from setup import run, setup
setup()

from datetime import datetime, timedelta
from pprint import pprint
import pickle

from analysis.backtest import ParamOptimizer
from analysis.strategy import PatternStrategy
from db import EXMongo

tf = '1h'


def calc_eta(combs, periods):
    eta_per_day = 3.8 / 90
    eta = 0

    if len(periods) == 2:
        eff = 1.3
    elif len(periods) == 4:
        eff = 1.7
    else:
        eff = 1.5

    for p in periods:
        eta += (p[1] - p[0]).days * eta_per_day

    eta = timedelta(seconds=int(eta * len(combs) / len(periods) * eff))
    return eta


def get_num_combs():
    with open(f'../data/combs_{tf}.pkl', 'rb') as f:
        combs = pickle.load(f)
    return len(combs)


async def find_optimal_paramters(mongo):

    test_periods = [
        # (datetime(2017, 1, 1), datetime(2017, 7, 1)),
        # (datetime(2017, 7, 1), datetime(2018, 1, 1)),

        # (datetime(2017, 1, 1), datetime(2017, 5, 1)),
        # (datetime(2017, 5, 1), datetime(2017, 9, 1)),
        # (datetime(2017, 9, 1), datetime(2018, 1, 1)),

        (datetime(2017, 1, 1), datetime(2017, 4, 1)),
        (datetime(2017, 4, 1), datetime(2017, 7, 1)),
        (datetime(2017, 7, 1), datetime(2017, 10, 1)),
        (datetime(2017, 10, 1), datetime(2018, 1, 1)),
    ]

    with open(f'../data/combs_{tf}.pkl', 'rb') as f:
        combs = pickle.load(f)

    ## Change section to test manually ##
    start = 5000
    end = 10000
    ## Total 70560
    #####################################

    print(f"Running optimization for {tf} {start}-{end}...(total {len(combs)})")

    combs = combs[start:end]

    eta = calc_eta(combs, test_periods)
    print()
    print(">> ETA:", eta)
    print()

    strategy = PatternStrategy('bitfinex')
    optimizer = ParamOptimizer(mongo, strategy)

    summaries = await optimizer.run(combs, test_periods)
    summary = optimizer.analyze_summary(summaries, 'best_params')
    summary.to_csv(f'../data/{tf}_optimization_{start}_{end}.csv')


def save_combinations(mongo):

    strategy = PatternStrategy('bitfinex')
    optimizer = ParamOptimizer(mongo, strategy)

    optimizer.optimize_selection('wvf_tf', [tf])
    optimizer.optimize_range('wvf_conf', 30, 80, 10)
    optimizer.optimize_range('wvf_lbsdh', 10, 40, 5)
    optimizer.optimize_range('wvf_bbl', 10, 40, 5)
    optimizer.optimize_range('wvf_bbsd', 1, 5, 1)
    optimizer.optimize_range('wvf_lbph', 30, 80, 10)
    optimizer.optimize_range('wvf_ph', 0.3, 1, 0.1)

    # optimizer.optimize_range('wvf_ltLB', 30, 80, 25)
    # optimizer.optimize_range('wvf_mtLB', 7, 20, 6)
    # optimizer.optimize_range('wvf_strg', 1, 10, 5)

    combs = optimizer.get_combinations()

    with open(f'../data/combs_{tf}.pkl', 'wb') as f:
        pickle.dump(combs, f)


async def main():
    mongo = EXMongo()

    # save_combinations(mongo)

    await find_optimal_paramters(mongo)

    # print(get_num_combs())


if __name__ == '__main__':
    run(main)


# Defualt values
# "wvf_conf": 50,
# "wvf_lbsdh": 22,
# "wvf_bbl": 20,
# "wvf_bbsd": 2.0,
# "wvf_lbph": 50,
# "wvf_ph": 0.85,
# "wvf_ltLB": 40,
# "wvf_mtLB": 14,
# "wvf_strg": 3
