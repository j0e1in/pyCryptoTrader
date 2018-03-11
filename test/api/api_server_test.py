from setup import setup, run
setup()

import asyncio

from api import APIServer
from db import EXMongo
from trading.trader import SingleEXTrader

# NOTE: To run in hot reload mode, use this command:
#       nodemon --exec python api_server_test.py --watch ../../lib/


async def main():

    mongo = EXMongo()
    trader = SingleEXTrader(mongo, 'bitfinex', 'pattern',
                            enable_trade=False,
                            log=False)
    server = APIServer(trader)

    await server.run()


if __name__ == "__main__":
    run(main)