from setup import setup, run
setup()

import asyncio

from db import EXMongo
from trading.trader import SingleEXTrader

log_file = 'start_trader.log'


async def main():

    mongo = EXMongo()
    trader = SingleEXTrader(mongo, 'bitfinex', 'pattern', log=True)

    await trader.start()
    await trader.ex.ex.close()


if __name__ == '__main__':
    run(main, debug=False, log_file=log_file)
