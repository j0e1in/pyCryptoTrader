from setup import setup, run
setup()

import asyncio
import argparse

from db import EXMongo
from trading.trader import SingleEXTrader

log_file = 'start_trader.log'


async def main():

    parser = argparse.ArgumentParser()
    parser.add_argument('--log-signal', action='store_true', help='Enable periodic indicator signal logging')
    argv = parser.parse_args()

    mongo = EXMongo()
    trader = SingleEXTrader(mongo, 'bitfinex', 'pattern', log=False, log_sig=argv.log_signal)

    await trader.start()
    await trader.ex.ex.close()


if __name__ == '__main__':
    run(main, debug=False, log_file=log_file)
