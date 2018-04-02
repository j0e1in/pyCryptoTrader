from setup import run


from api import APIServer
from db import EXMongo
from trading.trader import SingleEXTrader

# NOTE: To run in hot reload mode, use this command:
#       nodemon --exec python api_server_test.py --watch ../../lib/


async def main():

    mongo = EXMongo()
    trader = SingleEXTrader(mongo, 'bitfinex', 'pattern',
                            disable_trading=True,
                            log=True)
    server = APIServer(mongo, {'uid': trader})

    await server.run(access_log=True)


if __name__ == "__main__":
    run(main)
