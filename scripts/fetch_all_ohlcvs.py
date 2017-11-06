from ..setup import run, setup
setup()

import ccxt.async as ccxt
import motor.motor_asyncio as motor
import asyncio
from asyncio import ensure_future

from utils import combine, get_keys, get_constants, datetime_str, ms_sec
from hist_data import fetch_ohlcv_handler

consts = get_constants()


async def fetch_all_ohlcv():
    options = combine({
        'rateLimit': consts['rate_limit'],
        'enableRateLimit': True
    }, get_keys()['bitfinex'])

    start_str = datetime_str(2017, 1, 1)
    end_str = datetime_str(2017, 11, 1)

    exchange = ccxt.bitfinex2(options)
    await exchange.load_markets()

    res = fetch_ohlcv_handler(exchange, 'BTC/USD', start_str, end_str, '1m')
    async for candles in res:
        yield candles
        # for candle in candles:
        #     print(datetime.utcfromtimestamp(ms_sec(candle[0])))


async def fetch_ohlcv_to_mongo(coll):
    ops = []
    count = 0

    async for candles in fetch_all_ohlcv():
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
    mongo = motor.AsyncIOMotorClient('localhost', 27017)
    coll = mongo.exchange.bitfinex_ohlcv_5m
    await fetch_ohlcv_to_mongo(coll)


run_test(main)
