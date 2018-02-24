from setup import run, setup
setup()

import logging
import os

from db import EXMongo
from analysis.hist_data import build_ohlcv

logger = logging.getLogger()

async def main():
    target_tfs = [
        '1h',
        '2h',
        '3h',
        '4h',
        '5h',
        '6h',
        '7h',
        '8h',
        '9h',
        '10h',
        '11h',
        '12h',
        '15h',
        '18h',
    ]

    symbols = [
        "BTC/USD",
        "BCH/USD",
        "ETH/USD",
        "ETC/USD",
        "EOS/USD",
        "DASH/USD",
        "IOTA/USD",
        "LTC/USD",
        "NEO/USD",
        "OMG/USD",
        "XMR/USD",
        "XRP/USD",
        "ZEC/USD",
    ]

    src_tf = '1m'
    exchange = 'bitfinex'
    mongo = EXMongo()

    for symbol in symbols:
        for target_tf in target_tfs:
            logger.info(f"Building {exchange} {symbol} {target_tf} ohlcv")
            await build_ohlcv(
                mongo, exchange, symbol, src_tf, target_tf)

    # Starting from 'lib/'
    file = '../scripts/mongodb/create_index.js'
    os.system(f"mongo < {file}")


if __name__ == '__main__':
    run(main)
