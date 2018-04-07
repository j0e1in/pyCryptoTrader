from setup import run


import logging
import os

from db import EXMongo
from analysis.hist_data import build_ohlcv
from utils import tf_td, config, load_keys, rsym

logger = logging.getLogger('pyct')


def parse_args():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--from-start', action='store_true', help="Build ohlcvs from first data of source ohlcv")
    argv = parser.parse_args()

    return argv


async def main():
    argv = parse_args()

    src_tf = '1m'
    exchange = 'bitfinex'
    mongo = EXMongo()
    coll_prefix = ''

    target_tfs = config['analysis']['exchanges'][exchange]['timeframes_all']
    symbols = config['analysis']['exchanges'][exchange]['markets_all']

    for symbol in symbols:
        for target_tf in target_tfs:

            if argv.from_start:
                # Drop the collection
                coll = f"{coll_prefix}{exchange}_ohlcv_{rsym(symbol)}_{target_tf}"
                coll = mongo.get_collection(config['database']['dbname_exchange'], coll)
                await coll.drop()

                await build_ohlcv(mongo, exchange, symbol, src_tf, target_tf,
                                  upsert=True, coll_prefix=coll_prefix)
                logger.info(f"Building {exchange} {symbol} {target_tf} ohlcv from start")

            else:
                src_end_dt = await mongo.get_ohlcv_end(exchange, symbol, src_tf)
                target_end_dt = await mongo.get_ohlcv_end(exchange, symbol, target_tf)
                target_start_dt = target_end_dt - tf_td(target_tf) * 5
                logger.info(f"Building {exchange} {symbol} {target_tf} ohlcv "
                            f"from {target_start_dt} to {src_end_dt}")

                # Build ohlcv starting from 5 bars earlier from latest bar
                await build_ohlcv(mongo, exchange, symbol, src_tf, target_tf,
                                  start=target_start_dt, end=src_end_dt,
                                  upsert=True, coll_prefix=coll_prefix)

    # Build indexes
    if argv.from_start:
        # Starting from 'lib/'
        file = '../scripts/mongodb/create_index.js'
        host = f"{mongo.host}:{mongo.port}"
        auth = ''

        if mongo.config['auth']:
            host += f"/{mongo.config['auth_db']}"
            auth = f"-u {mongo.config['username']} -p {load_keys()['mongo_passwd']}"

        os.system(f"mongo {host} {auth} < {file}")


if __name__ == '__main__':
    run(main)
