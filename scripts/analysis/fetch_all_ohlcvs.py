from setup import run, setup
setup()

from datetime import datetime

import logging
import pymongo

from db import EXMongo
from analysis.hist_data import fetch_ohlcv
from utils import init_ccxt_exchange, execute_mongo_ops, config

logger = logging.getLogger()


start = datetime(2018, 2, 19)
end = datetime(2018, 2, 22)


async def fetch_ohlcv_to_mongo(coll, exchange, symbol, timeframe):
    ops = []
    count = 0

    res = fetch_ohlcv(exchange, symbol, start, end, timeframe)

    async for ohlcv in res:

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
            ops.append(
                pymongo.UpdateOne(
                    {'timestamp': rec['timestamp']},
                    {'$set': rec},
                    upsert=True))

            if len(ops) % 100000 == 0:
                await execute_mongo_ops(coll.bulk_write(ops))
                ops = []

        await execute_mongo_ops(coll.bulk_write(ops))


async def main():
    mongo = EXMongo()

    db = config['database']['dbname_exchange']
    ex = 'bitfinex'
    coll_tamplate = '{}_ohlcv_{}_{}'

    exchange = init_ccxt_exchange(ex + '2')

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

            await fetch_ohlcv_to_mongo(coll, exchange, symbol, timeframe)

            logger.info(f"Finished fetching {symbol} {timeframe}.")


if __name__ == '__main__':
    run(main)
