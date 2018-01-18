from setup import setup, run
setup()

import asyncio
import logging
import os
import sys

from db import EXMongo
from trading.trader import SingleEXTrader

log_file = 'start_trader.log'


async def main():

    mongo = EXMongo()
    trader = SingleEXTrader(mongo, 'bitfinex', 'pattern', log=True)

    await asyncio.gather(trader.start())


if __name__ == '__main__':
    run(main, debug=False, log_file=log_file)
