from setup import run


from datetime import datetime, timedelta
from pprint import pprint

import argparse
import logging
import pickle
import pymongo
import numpy as np
import pandas as pd
import sys

from analysis.backtest import ParamOptimizer
from analysis.strategy import PatternStrategy
from db import EXMongo
from utils import \
    INF, \
    config, \
    rsym, \
    utc_now, \
    tf_td, \
    roundup_dt, \
    rounddown_dt


logger = logging.getLogger('pyct')


def calc_eta(combs, period):
    eta_per_day = 4.2 / 90
    eta = (period[1] - period[0]).days * eta_per_day
    eff = 1.5

    eta = timedelta(seconds=int(eta * len(combs) / len(period) * eff))
    return eta

async def count_combs(mongo, argv):
    name = argv.name or ''
    coll_meta = mongo.get_collection(mongo.config['dbname_analysis'], f'param_set_meta')
    meta = await coll_meta.find_one({'name': name})
    return meta['count']


async def generate_params(mongo, ex, argv):
    name = argv.name or ''

    strategy = PatternStrategy(ex)
    optimizer = ParamOptimizer(mongo, strategy)

    optimizer.optimize_range('stochrsi_length', 10, 22, 2)
    optimizer.optimize_range('stoch_length', 8, 16, 2)
    optimizer.optimize_range('stochrsi_upper', 60, 80, 5)
    optimizer.optimize_range('stochrsi_lower', 20, 45, 5)
    optimizer.optimize_range('stochrsi_adx_length', 15, 40, 5)
    optimizer.optimize_range('stochrsi_di_length', 10, 14, 1)
    optimizer.optimize_range('stochrsi_rsi_length', 10, 20, 2)
    optimizer.optimize_range('stochrsi_rsi_mom_thresh', 10, 30, 10)

    combs = optimizer.count()
    print(f"Generating {combs} parameter sets of {name}")

    coll_meta = mongo.get_collection(mongo.config['dbname_analysis'], f'param_set_meta')
    coll = mongo.get_collection(mongo.config['dbname_analysis'], f'param_set_{name}')

    # Update meta data
    res = await coll_meta.remove({'name': name})
    await coll_meta.insert_one({
        'name': name,
        'columns': list(optimizer.param_d.keys()),
        'datetime': rounddown_dt(utc_now(), timedelta(minutes=1)),
        'count': 0,
    })

    # Drop old params collection
    res = await coll.drop()
    await coll.create_index([('idx', pymongo.ASCENDING)], unique=True)

    # Generate params
    buffer = []
    for i, params in enumerate(optimizer.get_combinations()):
        buffer.append({
            'idx': i+1,
            'params': params
        })

        if len(buffer) >= 10000:
            await coll.insert_many(buffer)
            buffer = []

    # Update total count in meta data
    count = await coll.count()
    await coll_meta.update({'name': name}, {'$set': {'count': count}})


async def optimize_params(mongo, ex, argv):
    name = argv.name or ''
    markets = argv.symbols and [m.strip() for m in argv.symbols.split(',')]

    coll_meta = mongo.get_collection(mongo.config['dbname_analysis'], f'param_set_meta')
    coll = mongo.get_collection(mongo.config['dbname_analysis'], f'param_set_{name}')

    if not await mongo.coll_exist(coll):
        raise ValueError(f"Parameter set `{name}` does not exist.")

    columns = (await coll_meta.find_one({'name': name}))['columns']
    combs = await coll.find({}, {'_id': False}).sort([('idx', 1)]).to_list(length=INF)

    idxs = np.array([c['idx'] for c in combs])
    params = np.array([c['params'] for c in combs])

    combs = pd.DataFrame(data=params, index=idxs, columns=columns)

    markets = markets or config['analysis']['exchanges'][ex]['markets_all']
    tftd = tf_td(config['analysis']['indicator_tf'])

    start = rounddown_dt(
        utc_now()-timedelta(days=config['analysis']['optimization_days']), tftd)
    end = rounddown_dt(utc_now(), tftd)
    period = (start, end)

    logger.info(f"Start optimizing {markets}")

    for market in markets:
        start_time = datetime.now()

        strategy = PatternStrategy(ex)
        optimizer = ParamOptimizer(mongo, strategy)

        await optimizer.run(combs, period, ex, market, name=name)

        end_time = datetime.now()
        logger.info(f"{market} optimization took {end_time-start_time}")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'task', type=str, help="Task to run. generate/optimize/count")

    # Options for all tasks
    parser.add_argument('--name', type=str, help="Name for the param set")
    parser.add_argument('--mongo-ssl', action='store_true', help='Add SSL files to mongo client')
    parser.add_argument('--mongo-host', type=str,
        help="Specify mongodb host,\n"
             "eg. localhost (host connect to mongo on host)\n"
             "    mongo (container connect to mongo container)\n"
             "    172.18.0.2 (host connect to mongo container)\n")

    # Options for optimize
    parser.add_argument('--symbols', type=str, help="Symbols to optimize, eg. --symbols='BTC/USD, ETH/USD'")

    argv = parser.parse_args()

    return argv


async def main():
    argv = parse_args()

    mongo = EXMongo(host=argv.mongo_host or None, ssl=argv.mongo_ssl)
    ex = 'bitfinex'

    if argv.task == 'generate':
        await generate_params(mongo, ex, argv)

    elif argv.task == 'optimize':
        await optimize_params(mongo, ex, argv)

    elif argv.task == 'count':
        print(await count_combs(mongo, argv))


if __name__ == '__main__':
    run(main)
