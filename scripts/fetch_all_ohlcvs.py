from setup import run, setup
setup()

from asyncio import ensure_future
from datetime import datetime
from pymongo.errors import BulkWriteError
from pprint import pprint

import asyncio
import ccxt.async as ccxt
import motor.motor_asyncio as motor
import logging

from hist_data import fetch_ohlcv
from utils import init_ccxt_exchange


logger = logging.getLogger()


async def fetch_all_ohlcv(exchange, symbol, timeframe):

    start = datetime(2017, 11, 1)
    end = datetime(2018, 1, 1)

    res = fetch_ohlcv(exchange, symbol, start, end, timeframe)
    async for ohlcv in res:
        yield ohlcv


async def fetch_ohlcv_to_mongo(coll, exchange, symbol, timeframe):
    ops = []
    count = 0

    async for ohlcv in fetch_all_ohlcv(exchange, symbol, timeframe):
        processed_ohlcv = []

        # [ MTS, OPEN, CLOSE, HIGH, LOW, VOLUME ]
        for oh in ohlcv:
            processed_ohlcv.append({
                'timestamp': oh[0],
                'open':      oh[1],
                'high':      oh[2],
                'low':       oh[3],
                'close':     oh[4],
                'volume':    oh[5]
            })

        ops.append(ensure_future(coll.insert_many(processed_ohlcv, ordered=False)))

        # insert 1000 ohlcv per op, clear up task stack periodically
        if len(ops) > 100:
            await asyncio.gather(*ops)
            ops = []

    await asyncio.gather(*ops)


async def main():
    ex = 'bitfinex'
    # ex_id = ex
    ex_id = ex+'2'
    coll_tamplate = '{}_ohlcv_{}_{}'

    exchange = init_ccxt_exchange(ex_id)

    mongo = motor.AsyncIOMotorClient('localhost', 27017)
    symbols = [
        "BTC/USD",
        "BCH/USD",
        "ETH/USD",
        "ETC/USD",
        "DASH/USD",
        "LTC/USD",
        "NEO/USD",
        "XMR/USD",
        "XRP/USD",
        "ZEC/USD",
    ]

    for sym in symbols:
        ohlcv_pairs = [
            (sym, '1m'),
            (sym, '5m'),
            (sym, '15m'),
            (sym, '30m'),
            (sym, '1h'),
            (sym, '3h'),
            (sym, '6h'),
            (sym, '12h'),
            (sym, '1d')
        ]

        ohlcv_pairs = ohlcv_pairs[::-1] # reverse the order

        for symbol, timeframe in ohlcv_pairs:
            _symbol = ''.join(symbol.split('/')) # remove '/'
            coll = getattr(mongo.exchange, coll_tamplate.format(ex, _symbol, timeframe))

            try:
                await fetch_ohlcv_to_mongo(coll, exchange, symbol, timeframe)
            except BulkWriteError as err:
                for msg in err.details['writeErrors']:
                    if 'duplicate' in msg['errmsg']:
                        continue
                    else:
                        pprint(err.details)
                        raise BulkWriteError(err)

            logger.info(f"Finished fetching {symbol} {timeframe}.")


if __name__ == '__main__':
    run(main)

