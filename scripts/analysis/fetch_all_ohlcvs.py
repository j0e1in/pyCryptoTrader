from setup import run, setup
setup()

from asyncio import ensure_future
from datetime import datetime, timedelta

import logging
import pymongo

from db import EXMongo
from analysis.hist_data import fetch_ohlcv
from utils import \
    init_ccxt_exchange, \
    execute_mongo_ops, \
    config, \
    utc_now

logger = logging.getLogger('pyct')


async def fetch_ohlcv_to_mongo(coll, exchange, symbol, timeframe, start, end, upsert=True):

    res = fetch_ohlcv(exchange, symbol, start, end, timeframe)
    bulk_ops = []

    async for ohlcv in res:
        ops = []

        if len(ohlcv) is 0:
            break

        # [ MTS, OPEN, CLOSE, HIGH, LOW, VOLUME ]
        for oh in ohlcv:
            rec = {
                'timestamp': oh[0],
                'open':      oh[1],
                'high':      oh[2],
                'low':       oh[3],
                'close':     oh[4],
                'volume':    oh[5]
            }

            if upsert:
                ops.append(
                    pymongo.UpdateOne(
                        {'timestamp': rec['timestamp']},
                        {'$set': rec},
                        upsert=True))
            else:
                ops.append(rec)

        if upsert:
            # Divide ops into 3 threads
            div = int(len(ops) / 3)
            bulk_ops = [
                coll.bulk_write(ops[:div]),
                coll.bulk_write(ops[div:div*2]),
                coll.bulk_write(ops[div*2:]),
            ]
            await execute_mongo_ops(bulk_ops)
        else:
            bulk_ops.append(ensure_future(coll.insert_many(ops)))
            if len(bulk_ops) > 10:
                await execute_mongo_ops(bulk_ops)
                ops = []

    if not upsert:
        await execute_mongo_ops(bulk_ops)


def parse_args():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--no-upsert', dest='upsert', action='store_false',
        help="Disable upsert while inserting data, can reduce insertion time and cpu usage, "
             "only use this option if no ohlcv in database")
    argv = parser.parse_args()

    return argv


async def main():
    argv = parse_args()

    mongo = EXMongo()

    db = config['database']['dbname_exchange']
    ex = 'bitfinex'
    coll_tamplate = '{}_ohlcv_{}_{}'

    exchange = init_ccxt_exchange(ex)

    symbols = config['analysis']['exchanges'][ex]['markets_all']

    for sym in symbols:
        ohlcv_pairs = [
            (sym, '1m'),
        ]

        ohlcv_pairs = ohlcv_pairs[::-1]  # reverse the order

        for symbol, timeframe in ohlcv_pairs:
            _symbol = ''.join(symbol.split('/'))  # remove '/'
            coll = mongo.get_collection(db, coll_tamplate.format(ex, _symbol, timeframe))
            start = await mongo.get_ohlcv_end(ex, symbol, timeframe) - timedelta(hours=5)
            end = utc_now()

            await fetch_ohlcv_to_mongo(coll, exchange, symbol, timeframe, start, end, upsert=argv.upsert)

            logger.info(f"Finished fetching {symbol} {timeframe}")

    exchange.close()


if __name__ == '__main__':
    run(main)
