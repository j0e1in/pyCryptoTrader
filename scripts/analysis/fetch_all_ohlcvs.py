from setup import run, setup
setup()

from asyncio import ensure_future
from datetime import datetime

import logging
import pymongo

from db import EXMongo
from analysis.hist_data import fetch_ohlcv
from utils import init_ccxt_exchange, execute_mongo_ops, config

logger = logging.getLogger()


start = datetime(2017, 8, 1)
end = datetime(2018, 2, 22)


async def fetch_ohlcv_to_mongo(coll, exchange, symbol, timeframe, upsert=True):

    res = fetch_ohlcv(exchange, symbol, start, end, timeframe)

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
            bulk_ops = ensure_future(coll.insert_many(ops))
            await execute_mongo_ops(bulk_ops)


async def main():
    mongo = EXMongo()

    db = config['database']['dbname_exchange']
    ex = 'bitfinex'
    coll_tamplate = '{}_ohlcv_{}_{}'

    exchange = init_ccxt_exchange(ex + '2')

    upsert = False

    symbols = [
        "BTC/USD",
        "BCH/USD",
        "ETH/USD",
        "ETC/USD",
        "EOS/USD",
        "DASH/USD",
        "IOTA/USD",
        "LTC/USD",
        "NEO/USD",
        "OMG/USD",
        "XMR/USD",
        "XRP/USD",
        "ZEC/USD",
    ]

    for sym in symbols:
        ohlcv_pairs = [
            (sym, '1m'),
        ]

        ohlcv_pairs = ohlcv_pairs[::-1]  # reverse the order

        for symbol, timeframe in ohlcv_pairs:
            _symbol = ''.join(symbol.split('/'))  # remove '/'
            coll = mongo.get_collection(db, coll_tamplate.format(ex, _symbol, timeframe))

            await fetch_ohlcv_to_mongo(coll, exchange, symbol, timeframe, upsert=upsert)

            logger.info(f"Finished fetching {symbol} {timeframe}.")


if __name__ == '__main__':
    run(main)
