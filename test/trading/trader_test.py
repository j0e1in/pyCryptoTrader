from setup import setup, run
setup()

from pprint import pprint
import asyncio

from db import EXMongo
from trading.exchange import Bitfinex
from trading.trader import SingleEXTrader
from utils import get_project_root, load_keys

loop = asyncio.get_event_loop()


def test_trader_start(trader):
    trader.start()


def test_start_trading(trader):
    loop.run_until_complete(trader.start_trading())
    pprint(trader.ohlcv)


def main():
    mongo = EXMongo()
    trader = SingleEXTrader(mongo, 'bitfinex')

    # test_trader_start(trader)
    test_start_trading(trader)


if __name__ == '__main__':
    run(main)
