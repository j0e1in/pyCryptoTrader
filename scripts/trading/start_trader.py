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
    parser.add_argument('--disable-trade', dest='enable_trade', action='store_false', help='Disable creating orders')
    parser.add_argument('--ssl', action='store_true', help='Enable SSL, only works if API is enabled')
    argv = parser.parse_args()

    return argv


async def main():
    argv = parse_args()

    mongo = EXMongo()
    trader = SingleEXTrader(mongo, 'bitfinex', 'pattern',
            log=argv.log,
            log_sig=argv.log_signal,
            enable_trade=argv.enable_trade)

    if argv.enable_api:
        with_ssl = 'with' if argv.ssl else 'without'
        logger.info(f"Starting API server {with_ssl} SSL...")

        server = APIServer(trader)
        await server.run(access_log=True, enable_ssl=argv.ssl)

    else:
        await trader.start()
        await trader.ex.ex.close()


if __name__ == '__main__':
    run(main, debug=False, log_file=log_file)
