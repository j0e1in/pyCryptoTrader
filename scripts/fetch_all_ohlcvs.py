from setup import run, setup
setup()

import ccxt.async as ccxt
import motor.motor_asyncio as motor
import asyncio
from asyncio import ensure_future
import logging

from utils import init_ccxt_exchange, utc_ts
from hist_data import fetch_ohlcv_handler


logger = logging.getLogger()


async def fetch_all_ohlcv(exchange, symbol, timeframe):

    start = utc_ts(2017, 1, 1)
    end = utc_ts(2017, 11, 1)

    await exchange.load_markets()
    res = fetch_ohlcv_handler(exchange, symbol, start, end, timeframe)
    async for candles in res:
        yield candles


async def fetch_ohlcv_to_mongo(coll, exchange, symbol, timeframe):
    ops = []
    count = 0

    async for candles in fetch_all_ohlcv(exchange, symbol, timeframe):
        processed_candles = []

        # [ MTS, OPEN, CLOSE, HIGH, LOW, VOLUME ]
        for cand in candles:
            processed_candles.append({
                'timestamp': cand[0],
                'open':     cand[1],
                'close':    cand[2],
                'high':     cand[3],
                'low':      cand[4],
                'volume':   cand[5]
            })

        ops.append(ensure_future(coll.insert_many(processed_candles)))

        # insert 1000 candles per op, clear up task stack periodically
        if len(ops) > 50:
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
        'BCH/USD',
        'XRP/USD',
        'XMR/USD',
        'NEO/USD',
        'ZEC/USD',
        'DASH/USD',
        'ETC/USD',
        'LTC/USD'
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
            await fetch_ohlcv_to_mongo(coll, exchange, symbol, timeframe)
            logger.info(f"Finished fetching {symbol} {timeframe}.")


run(main)
