from setup import setup, run
setup()

import asyncio
import argparse
import logging

from api import APIServer
from db import EXMongo
from trading.trader import SingleEXTrader

log_file = 'start_trader.log'
logger = logging.getLogger()


def parse_args():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='0.0.0.0', help='Server IP')
    parser.add_argument('--port', type=int, default=8000, help='Server port')
    parser.add_argument('--log', action='store_true', help='Enable trader logging')
    parser.add_argument('--log-signal', action='store_true', help='Enable periodic indicator signal logging')
    parser.add_argument('--enable-api', action='store_true', help='Enable API server for clients to request data')
    parser.add_argument('--disable-trading', dest='enable_trade', action='store_false', help='Disable creating orders')
    parser.add_argument('--ssl', action='store_true', help='Enable SSL, only works if API is enabled')
    parser.add_argument('--mongo-host', type=str, help="Specify mongodb host,\n"
                                                       "eg. localhost (host connect to mongo on host)\n"
                                                       "    mongo (container connect to mongo container)\n"
                                                       "    172.18.0.2 (host connect to mongo container)\n")
    argv = parser.parse_args()

    return argv


async def main():
    argv = parse_args()

    mongo_host = argv.mongo_host if argv.mongo_host else None
    mongo = EXMongo(host=mongo_host)

    trader = SingleEXTrader(mongo, 'bitfinex', 'pattern',
            log=argv.log,
            log_sig=argv.log_signal,
            enable_trade=argv.enable_trade)

    if argv.enable_api:
        server = APIServer(trader)
        await server.run(access_log=True, enable_ssl=argv.ssl)

    else:
        await trader.start()
        await trader.ex.ex.close()


if __name__ == '__main__':
    run(main, debug=False, log_file=log_file)
