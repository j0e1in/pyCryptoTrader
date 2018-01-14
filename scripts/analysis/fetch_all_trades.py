from setup import run, setup
setup()

from asyncio import ensure_future
from datetime import datetime

import asyncio
import ccxt.async as ccxt
import motor.motor_asyncio as motor
import logging

from analysis.hist_data import fetch_trades
from utils import init_ccxt_exchange, execute_mongo_ops


logger = logging.getLogger()


start = datetime(2017, 11, 1)
end = datetime(2018, 1, 1)


async def fetch_trades_to_mongo(coll, exchange, symbol):
    ops = []
    count = 0

    res = fetch_trades(exchange, symbol, start, end)
    async for trades in res:
        processed_trades = []

        # [ MTS, OPEN, CLOSE, HIGH, LOW, VOLUME ]
        for trd in trades:
            del trd['datetime']
            del trd['info']
            del trd['type']
            processed_trades.append(trd)

        ops.append(ensure_future(coll.insert_many(processed_trades)))

        # insert ~1000 trades per op, clean up task stack periodically
        if len(ops) > 50:
            await execute_mongo_ops(ops)
            ops = []

    await execute_mongo_ops(ops)


async def main():
    ex = 'bitfinex'
    exchange = init_ccxt_exchange(ex + '2')

    coll_tamplate = '{}_trades_{}'

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

    for symbol in symbols:
        _symbol = ''.join(symbol.split('/')) # remove '/'
        coll = getattr(mongo.exchange, coll_tamplate.format(ex, _symbol))
        await fetch_trades_to_mongo(coll, exchange, symbol)
        logger.info(f"Finished fetching {symbol}.")


if __name__ == '__main__':
    run(main)
