from setup import run, setup
setup()

import logging
import os

from db import EXMongo
from analysis.hist_data import build_ohlcv
from utils import timeframe_timedelta

logger = logging.getLogger()


async def main():
    target_tfs = [
        '15m',
        '30m',
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

    build_from_start = False

    src_tf = '1m'
    exchange = 'bitfinex'
    mongo = EXMongo()

    for symbol in symbols:
        for target_tf in target_tfs:
            logger.info(f"Building {exchange} {symbol} {target_tf} ohlcv")

            if build_from_start:
                await build_ohlcv(mongo, exchange, symbol, src_tf, target_tf, upsert=False)

            else:
                src_end_dt = await mongo.get_ohlcv_end(exchange, symbol, src_tf)
                target_end_dt = await mongo.get_ohlcv_end(exchange, symbol, target_tf)
                target_start_dt = target_end_dt - timeframe_timedelta(target_tf) * 5

                # Build ohlcv starting from 5 bars earlier from latest bar
                await build_ohlcv(mongo, exchange, symbol, src_tf, target_tf,
                                start=target_start_dt, end=src_end_dt, upsert=True)

    # Starting from 'lib/'
    file = '../scripts/mongodb/create_index.js'
    os.system(f"mongo < {file}")


if __name__ == '__main__':
    run(main)
