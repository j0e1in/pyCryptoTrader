from setup import run, setup
setup()

import ccxt.async as ccxt
import motor.motor_asyncio as motor
import asyncio
from asyncio import ensure_future
from datetime import datetime
import logging

from utils import init_exchange, datetime_str
from hist_data import fetch_ohlcv_handler

logger = logging.getLogger()



async def fetch_all_ohlcv(exchange, symbol, timeframe):

    start_str = datetime_str(2017, 1, 1)
    end_str = datetime_str(2017, 11, 1)

    await exchange.load_markets()
    res = fetch_ohlcv_handler(exchange, symbol, start_str, end_str, timeframe)
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

        # insert 120 candles per op, clear up task stack periodically
        if len(ops) > 1000:
            await asyncio.gather(*ops)
            ops = []


async def main():
    exchange = init_exchange('bitfinex2')
    coll_tamplate = 'bitfinex_ohlcv_{}_{}'

    mongo = motor.AsyncIOMotorClient('localhost', 27017)
    ohlcv_pairs = [('BTC/USD', '30m')]
    ohlcv_pairs = ohlcv_pairs[::-1] # reverse the order

    for symbol, timeframe in ohlcv_pairs:
        _symbol = ''.join(symbol.split('/')) # remove '/'
        coll = getattr(mongo.exchange, coll_tamplate.format(_symbol, timeframe))
        await fetch_ohlcv_to_mongo(coll, exchange, symbol, timeframe)
        logger.info(f"Finished fetching {symbol} {timeframe}.")


run(main)
