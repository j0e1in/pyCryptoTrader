from setup import run, setup
setup()

import ccxt.async as ccxt
import motor.motor_asyncio as motor
import asyncio
from asyncio import ensure_future
from datetime import datetime
import logging

from utils import combine, get_keys, get_constants, datetime_str, ms_sec
from hist_data import fetch_ohlcv_handler

consts = get_constants()
logger = logging.getLogger()

def init_exchange(exchange_id):
    options = combine({
        'rateLimit': consts['rate_limit'],
        'enableRateLimit': True
    }, get_keys()[exchange_id])

    exchange = getattr(ccxt, exchange_id)(options)
    return exchange


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
    ohlcv_pairs = [('ETH/USD', '1m'), ('ETH/USD', '5m'), ('ETH/USD', '15m'), ('ETH/USD', '30m'), ('ETH/USD', '1h')]
    ohlcv_pairs = ohlcv_pairs[::-1] # reverse the order

    for symbol, timeframe in ohlcv_pairs:
        coll = getattr(mongo.exchange, coll_tamplate.format(symbol, timeframe))
        await fetch_ohlcv_to_mongo(coll, exchange, symbol, timeframe)
        logger.info(f"Finished fetching {symbol} {timeframe}, wait for 5 min before continue...")
        asyncio.sleep(300) # sleep for 5 min when finished one round


run(main)
