from setup import setup, run
setup()

import asyncio
import argparse

from api import APIServer
from db import EXMongo
from trading.trader import SingleEXTrader

log_file = 'start_trader.log'


async def main():

    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='0.0.0.0', help='Server IP')
    parser.add_argument('--port', type=int, default=8000, help='Server port')
    parser.add_argument('--enable-api', action='store_true', help='Enable API server for clients to request data')
    parser.add_argument('--log-signal', action='store_true', help='Enable periodic indicator signal logging')
    argv = parser.parse_args()

    mongo = EXMongo()
    trader = SingleEXTrader(mongo, 'bitfinex', 'pattern', log=False, log_sig=argv.log_signal)

    if argv.enable_api:
        server = APIServer(trader)
        await server.run(access_log=True)

    else:
        await trader.start()
        await trader.ex.ex.close()


if __name__ == '__main__':
    run(main, debug=False, log_file=log_file)
