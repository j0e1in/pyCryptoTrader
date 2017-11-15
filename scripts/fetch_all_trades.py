from setup import run, setup
setup()

import ccxt.async as ccxt
import motor.motor_asyncio as motor
import asyncio
from asyncio import ensure_future
import logging

from utils import exchange_timestamp, ms_sec, init_exchange, utcms_dt
from hist_data import fetch_trades_handler


logger = logging.getLogger()


async def fetch_all_trades(exchange, symbol):

    start = exchange_timestamp(2017, 1, 1)
    end = exchange_timestamp(2017, 11, 1)

    await exchange.load_markets()
    res = fetch_trades_handler(exchange, symbol, start, end)
    async for trades in res:
        yield trades


async def fetch_trades_to_mongo(coll, exchange, symbol):
    ops = []
    count = 0

    async for trades in fetch_all_trades(exchange, symbol):
        processed_trades = []

        # [ MTS, OPEN, CLOSE, HIGH, LOW, VOLUME ]
        for trd in trades:
            del trd['datetime']
            del trd['info']
            del trd['type']
            processed_trades.append(trd)

        ops.append(ensure_future(coll.insert_many(processed_trades)))

        # insert ~120 trades per op, clear up task stack periodically
        if len(ops) > 50:
            await asyncio.gather(*ops)
            ops = []


async def main():
    exchange = init_exchange('bitfinex2')

    coll_tamplate = 'bitfinex_trades_{}'

    mongo = motor.AsyncIOMotorClient('localhost', 27017)
    symbols = ['ETH/USD']

    for symbol in symbols:
        _symbol = ''.join(symbol.split('/')) # remove '/'
        coll = getattr(mongo.exchange, coll_tamplate.format(_symbol))
        await fetch_trades_to_mongo(coll, exchange, symbol)
        logger.info(f"Finished fetching {symbol}.")




run(main)