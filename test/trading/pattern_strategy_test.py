from setup import run


from datetime import timedelta
from pprint import pprint

import asyncio
import logging
import numpy as np
import pandas as pd

from db import EXMongo
from trading.indicators import Indicator
from trading.strategy import Signals
from trading.trader import SingleEXTrader
from utils import \
    config, \
    utc_now, \
    tf_td, \
    roundup_dt, \
    rounddown_dt

logger = logging.getLogger('pyct')


async def test_signal_start(sig):
    await sig.start()


async def main():
    mongo = EXMongo()
    sig = Signals(mongo, 'bitfinex', Indicator())

    await test_signal_start(sig)


if __name__ == '__main__':
    run(main, debug=False)