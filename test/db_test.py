from setup import run, setup
setup()

import motor.motor_asyncio as motor

from db import EXMongo
from utils import exchange_timestamp, init_exchange

from pprint import pprint as pp


async def main():
    exchange = init_exchange('bitfinex2')
    mongo = EXMongo()

    start = exchange_timestamp(2017, 10, 1)
    end = exchange_timestamp(2017, 10, 2)
    res = await mongo.get_ohlcv(exchange, 'BTC/USD', start, end, '15m')



run(main)