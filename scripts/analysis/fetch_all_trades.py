from setup import run

from asyncio import ensure_future
from datetime import timedelta

import asyncio
import ccxt.async as ccxt
import motor.motor_asyncio as motor
import logging

from analysis.hist_data import fetch_trades
from db import EXMongo
from utils import \
    init_ccxt_exchange, \
    execute_mongo_ops, \
    config, \
    utc_now

logger = logging.getLogger('pyct')


async def fetch_trades_to_mongo(coll, exchange, symbol, start, end):
    ops = []

    res = fetch_trades(exchange, symbol, start, end)
    async for trades in res:
        processed_trades = []

        # [ MTS, OPEN, CLOSE, HIGH, LOW, VOLUME ]
        for trd in trades:
            trd.pop('datetime')
            trd.pop('info')
            trd.pop('type')
            processed_trades.append(trd)

        ops.append(ensure_future(coll.insert_many(processed_trades)))

        # insert ~1000 trades per op, clean up task stack periodically
        if len(ops) > 10:
            await execute_mongo_ops(ops)
            ops = []

    await execute_mongo_ops(ops)


def parse_args():
    import argparse

    parser = argparse.ArgumentParser()
    argv = parser.parse_args()

    return argv


async def main():
    argv = parse_args()

    mongo = EXMongo()

    db = config['database']['dbname_exchange']
    ex = 'bitfinex'
    coll_tamplate = '{}_trades_{}'

    exchange = init_ccxt_exchange(ex)

    symbols = config['analysis']['exchanges'][ex]['markets_all']

    for symbol in symbols:
        _symbol = ''.join(symbol.split('/'))  # remove '/'
        coll = mongo.get_collection(db, coll_tamplate.format(ex, _symbol))
        start = await mongo.get_trades_end(ex, symbol) - timedelta(hours=1)
        end = utc_now()

        await fetch_trades_to_mongo(coll, exchange, symbol, start, end)

        logger.info(f"Finished fetching {symbol}.")

    await exchange.close()


if __name__ == '__main__':
    run(main)
