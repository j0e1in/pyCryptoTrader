from setup import setup, run
setup()

from datetime import timedelta
from pprint import pprint

import asyncio
import logging
import numpy as np
import pandas as pd

from db import EXMongo
from trading.trader import SingleEXTrader
from utils import \
    config, \
    utc_now, \
    tf_td, \
    roundup_dt, \
    rounddown_dt

logger = logging.getLogger('pyct')


async def test_execute(trader):
    print('-- Execute --')

    async def run(sig_conf, sig_dt, market, expect_action):
        sig = {}
        sig[market] = pd.Series(sig_conf, index=sig_dt)
        actions = await trader.strategy.execute(sig)

        if actions[market] != expect_action:
            logger.error(f"Expect {expect_action} but get {actions[market]}")

        return sig

    tftd = tf_td(trader.config['indicator_tf'])
    buffer_time = tftd / 20
    market = trader.ex.markets[0]
    trader.ex.markets = [market]

    interval_start = rounddown_dt(utc_now(), tftd)
    interval_end = roundup_dt(interval_start, tftd)
    interval_start2 = interval_end
    interval_end2 = roundup_dt(interval_start2, tftd)

    sig_len = 10
    sig_dt = []
    sig_conf = []
    first_dt = interval_start - tftd * (sig_len - 1)

    for i in range(sig_len):
        sig_dt.append(first_dt + tftd * i)
        sig_conf.append(np.nan)

    print('\n--Test 1-- Near start | Has no signal')
    sig_dt[-1] = interval_start + tftd / 20
    await run(sig_conf, sig_dt, market, 'NONE')

    print('\n--Test 2-- Not near_start/end | Has signal')
    sig_conf[-1] = 100
    sig_dt[-1] = interval_start + tftd / 9
    await run(sig_conf, sig_dt, market, 'NONE')

    print('\n--Test 3-- Not near_start/end | Change signal')
    sig_conf[-1] = -100
    sig_dt[-1] = interval_start + tftd / 5
    await run(sig_conf, sig_dt, market, 'NONE')

    print('\n--Test 4-- Near_end | Has signal')
    sig_conf[-1] = 100
    sig_dt[-1] = interval_end - tftd / 4
    await run(sig_conf, sig_dt, market, 'BUY')

    print('\n--Test 5-- Near_end | Signal is the same')
    sig_conf[-1] = 100
    sig_dt[-1] += buffer_time * 1 / 3
    await run(sig_conf, sig_dt, market, 'NONE')

    print('\n--Test 6-- Near_end | In buffer time | Change signal')
    sig_conf[-1] = np.nan
    sig_dt[-1] += buffer_time * 1 / 3
    await run(sig_conf, sig_dt, market, 'NONE')

    print('\n--Test 7-- Near_end | Not in buffer time | Change signal')
    sig_conf[-1] = np.nan
    sig_dt[-1] += buffer_time * 1 / 3
    await run(sig_conf, sig_dt, market, 'CANCEL')

    print('\n--Test 8-- Near_end | Not in buffer time | Signal reactivated')
    sig_conf[-1] = 100
    sig_dt[-1] += buffer_time
    await run(sig_conf, sig_dt, market, 'BUY')

    print('\n--Test 9-- Near_start | Signal changed at last minute')
    sig_conf.append(np.nan)
    sig_dt.append(interval_start2)
    sig_conf[-2] = -100
    sig_dt[-2] = interval_start
    await run(sig_conf, sig_dt, market, 'SELL')

    print('\n--Test 10-- Near_start | Last interval executed | New signal changed')
    sig_conf[-1] = 100
    sig_dt[-1] = interval_start2 + tftd / 15
    await run(sig_conf, sig_dt, market, 'NONE')



async def main():
    mongo = EXMongo()
    trader = SingleEXTrader(mongo, 'bitfinex', 'pattern', log=True, disable_trading=True)

    await test_execute(trader)

    await trader.ex.ex.close()


if __name__ == '__main__':
    run(main, debug=False)