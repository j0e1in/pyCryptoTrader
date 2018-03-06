from setup import run, setup
setup()

from datetime import datetime, timedelta
from pprint import pprint

import argparse
import pickle
import sys

from analysis.backtest import ParamOptimizer
from analysis.strategy import PatternStrategy
from db import EXMongo
from utils import config


def calc_eta(combs, periods):
    eta_per_day = 4.2 / 90
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


def get_num_combs(argv):
    prefix = argv.prefix + '_' if argv.prefix else ''

    with open(f'../data/{prefix}combs.pkl', 'rb') as f:
        combs = pickle.load(f)

    return len(combs)


async def find_optimal_paramters(mongo, argv):
    tf = config['analysis']['indicator_tf']
    prefix = argv.prefix + '_' if argv.prefix else ''

    with open(f'../data/{prefix}combs.pkl', 'rb') as f:
        combs = pickle.load(f)

    start = argv.start if argv.start else 1
    end = argv.end if argv.end else len(combs)

    test_periods = [
        (datetime(2017, 8, 1), datetime(2018, 3, 5)),
        # (datetime(2017, 2, 1), datetime(2018, 3, 5)),
    ]

    print(f"Running optimization for {tf} {start}-{end}...(total {len(combs)})")

    combs = combs[start-1:end]

    eta = calc_eta(combs, test_periods)
    print()
    print(">> ETA:", eta)
    print()

    strategy = PatternStrategy('bitfinex')
    optimizer = ParamOptimizer(mongo, strategy)

    summaries = await optimizer.run(combs, test_periods)
    summary = optimizer.analyze_summary(summaries, 'best_params')
    summary.to_csv(f'../data/{prefix}{tf}_optimization_{start}_{end}.csv')


def generate_params(mongo, argv):
    prefix = argv.prefix + '_' if argv.prefix else ''

    strategy = PatternStrategy('bitfinex')
    optimizer = ParamOptimizer(mongo, strategy)

    # optimizer.optimize_range('dmi_adx_length', 30, 46, 3)
    # optimizer.optimize_range('dmi_di_length', 10, 14, 1)
    # optimizer.optimize_range('dmi_base_thresh', 16, 26, 2)
    # optimizer.optimize_range('dmi_adx_thresh', 25, 40, 3)
    # optimizer.optimize_range('dmi_di_top_thresh', 25, 40, 3)
    # optimizer.optimize_range('dmi_di_bot_thresh', 13, 19, 2)
    # optimizer.optimize_range('dmi_adx_top_peak_diff', 0.6, 1.2, 0.2)
    # optimizer.optimize_range('dmi_adx_bot_peak_diff', 0.6, 1.2, 0.2)
    # optimizer.optimize_range('dmi_di_diff', 10, 20, 2)
    # optimizer.optimize_range('dmi_ema_length', 7, 13, 2)

    optimizer.optimize_range('stoch_rsi_length', 10, 20, 2)
    optimizer.optimize_range('stoch_length', 8, 14, 2)
    optimizer.optimize_range('stochrsi_upper', 60, 80, 5)
    optimizer.optimize_range('stochrsi_lower', 20, 40, 5)
    optimizer.optimize_range('stochrsi_adx_length', 20, 40, 5)
    optimizer.optimize_range('stochrsi_di_length', 10, 14, 1)
    optimizer.optimize_range('stochrsi_rsi_length', 10, 20, 2)
    optimizer.optimize_range('stochrsi_rsi_mom_thresh', 10, 30, 10)

    combs = optimizer.get_combinations()
    print(f"Generated {len(combs)} sets of parameter settings.")

    with open(f'../data/{prefix}combs.pkl', 'wb') as f:
        pickle.dump(combs, f)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('task', type=str, help="Task to run. generate/optimize/count")

    # Options all tasks
    parser.add_argument('--prefix', type=str, help="Prefix for param .pkl file, eg. 'pre' => 'pre_combs' ")

    # Options for optimization
    parser.add_argument('--start', '-s', type=int, help="Integer, starting parameter set to optimize.")
    parser.add_argument('--end', '-e',  type=int, help="Integer, ending parameter set to optimize.")

    argv = parser.parse_args()

    return argv


async def main():
    argv = parse_args()

    mongo = EXMongo()

    if argv.task == 'generate':
        # Generate parameter sets and save to .pkl
        generate_params(mongo, argv)

    elif argv.task == 'optimize':
        # Load saved pkl and run specific range of sets.
        await find_optimal_paramters(mongo, argv)

    elif argv.task == 'count':
        # Load pkl and print number of parameter sets
        print(get_num_combs(argv))


if __name__ == '__main__':
    run(main)
