from setup import run

from concurrent.futures import FIRST_COMPLETED
import asyncio

from db import EXMongo
from trading import SingleEXTrader
from utils import config


async def close_position(trader, symbol):

    if symbol not in trader.ex.markets:
        trader.ex.markets.append(symbol)

    done, pending = await asyncio.wait(
        [
            trader.ex.update_markets(),
            trader.ex.update_trade_fees(),
            trader.close_position(symbol, type='limit'),
        ],
        return_when=FIRST_COMPLETED)


def parse_args():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--uid', type=str, help='Trader uid')
    parser.add_argument('-s', '--symbol', type=str, help='Symbol of positions to close')
    argv = parser.parse_args()

    return argv


async def main():
    argv = parse_args()

    mongo = EXMongo()
    trader = SingleEXTrader(
        mongo, 'bitfinex', 'pattern', uid=argv.uid, log=True, reset_state=True)

    if not argv.uid or not argv.symbol:
        argv.print_help()
    else:
        await close_position(trader, argv.symbol)


if __name__ == '__main__':
    run(main)