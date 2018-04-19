from setup import run


from pprint import pformat

import argparse
import logging

from db import EXMongo
from trading.trader import SingleEXTrader
from trading.exchanges import EXBase
from utils import config

logger = logging.getLogger('pyct')


def parse_args():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--symbols', type=str, help="Symbols to fetch, eg. --symbols=BTC/USD,ETH/USD")
    parser.add_argument('--rate-limit', type=int, help="Fetch ohlcv request rate (in ms)")
    parser.add_argument('--mongo-ssl', action='store_true', help='Add SSL files to mongo client')
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

    if argv.symbols:
        markets = argv.symbols.split(',')
    else:
        # Let ohlcv stream fetch all markets
        markets = config['trading']['bitfinex']['markets_all']

    config['trading']['bitfinex']['markets'] = markets

    logger.info(f"Start fetching markets:\n" \
                f"{pformat(config['trading']['bitfinex']['markets'])}")

    mongo_host = argv.mongo_host if argv.mongo_host else None
    mongo = EXMongo(host=mongo_host, ssl=argv.mongo_ssl)

    ex = EXBase(mongo, 'bitfinex', log=True)

    await ex._start_ohlcv_stream(build_ohlcv=True)
    await ex.ex.close()



if __name__ == '__main__':
    run(main)
