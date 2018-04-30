from setup import run

from datetime import datetime, timedelta

import asyncio
import logging

from db import EXMongo
from trading.indicators import Indicator
from trading.strategy import series_equal
from utils import tf_td

logger = logging.getLogger('pyct')


async def test_signal_consistency(mongo, strategy):
    """ Test signal consistency. """
    ind = Indicator()
    strgy = getattr(ind, strategy)

    ex = 'bitfinex'
    symbols = [
        "BTC/USD",
        "BCH/USD",
        "DASH/USD",
        "ETH/USD",
        "ETC/USD",
        "EOS/USD",
        "IOTA/USD",
        "NEO/USD",
        "OMG/USD",
        "XMR/USD",
        "XRP/USD",
        "ZEC/USD",
    ]
    tf = '8h'
    days = 60
    m = -20
    start = datetime(2018, 2, 1)

    params = await mongo.get_params(ex)
    s = e = None

    for symbol in symbols:
        ind.p = params[symbol]

        prev_oh = None
        prev_sig = None

        for i in range(80):
            s = start + tf_td(tf) * i
            e = s + timedelta(days=days)

            oh = await mongo.get_ohlcv(ex, symbol, tf, s, e)
            sig = strgy(oh)

            if prev_oh is not None and prev_sig is not None:
                tt = oh.loc[oh.index[m:].intersection(prev_oh.index[m:])]
                ss = prev_oh.loc[prev_oh.index[m:].intersection(tt.index[m:])]

                yy = sig.loc[sig.index[m:].intersection(prev_sig.index[m:])]
                xx = prev_sig.loc[prev_sig.index[m:].intersection(yy.index[m:])]

                # from ipdb import set_trace; set_trace()

                if not series_equal(ss.open, tt.open):
                    logger.warning(f"{symbol} ohlcv.open is not consistent")
                if not series_equal(ss.close, tt.close):
                    logger.warning(f"{symbol} ohlcv.close is not consistent")
                if not series_equal(ss.high, tt.high):
                    logger.warning(f"{symbol} ohlcv.high is not consistent")
                if not series_equal(ss.low, tt.low):
                    logger.warning(f"{symbol} ohlcv.low is not consistent")
                if not series_equal(xx, yy):
                    logger.warning(f"{symbol} signal is not consistent")

            prev_oh = oh
            prev_sig = sig
            # asyncio.sleep(2)

    logger.info(f'end: {e}')


async def main():
    mongo = EXMongo()

    await test_signal_consistency(mongo, 'stoch_rsi_sig')


if __name__ == '__main__':
    run(main)