from setup import setup, run
setup()

from pprint import pformat

import asyncio
import argparse
import logging

from api import APIServer
from db import EXMongo
from trading.trader import SingleEXTrader
from utils import config

logger = logging.getLogger('pyct')

def parse_args():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--rate-limit', type=int, help="Fetch ohlcv request rate (in ms)")
    parser.add_argument('--mongo-host', type=str, help="Specify mongodb host,\n"
                                                       "eg. localhost (host connect to mongo on host)\n"
                                                       "    mongo (container connect to mongo container)\n"
                                                       "    172.18.0.2 (host connect to mongo container)\n")
    argv = parser.parse_args()

    return argv


async def main():
    argv = parse_args()

    config['ccxt']['rate_limit'] = \
        argv.rate_limit if argv.rate_limit else 4000

    # Let ohlcv stream fetch all markets
    config['trading']['bitfinex']['markets'] = \
        config['trading']['bitfinex']['markets_all']

    logger.info(f"Start fetching markets:\n" \
                f"{pformat(config['trading']['bitfinex']['markets'])}")

    mongo_host = argv.mongo_host if argv.mongo_host else None
    mongo = EXMongo(host=mongo_host)

    trader = SingleEXTrader(mongo, 'bitfinex', 'pattern',
            custom_config=config,
            disable_trading=True, log=True)

    # Start only ohlcv stream
    await trader.ex._start_ohlcv_stream()
    await trader.ex.ex.close()


if __name__ == '__main__':
    run(main)
