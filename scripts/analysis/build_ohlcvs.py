from setup import run, setup
setup()

from db import EXMongo
import logging

from analysis.hist_data import build_ohlcv

logger = logging.getLogger()

async def main():
    target_tfs = [
        '2h',
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
        "DASH/USD",
        "LTC/USD",
        "NEO/USD",
        "XMR/USD",
        "XRP/USD",
        "ZEC/USD",
    ]

    src_tf = '1h'
    exchange = 'bitfinex'
    mongo = EXMongo()

    for symbol in symbols:
        for target_tf in target_tfs:
            logger.info(f"Building {exchange} {symbol} {target_tf} ohlcv")
            await build_ohlcv(
                mongo, exchange, symbol, src_tf, target_tf)


if __name__ == '__main__':
    run(main)
