from setup import run, setup
setup()

from pprint import pprint as pp

from backtest import Backtest
from mongo import Mongo
from utils import datetime_str
import strategy


async def main():
    mongo = Mongo(host='localhost', port=27017)

    options = {
        'strategy': strategy.pattern_strategy,
        'exchange': 'bitfinex',
        'symbol': 'ETH/USD',
        'fund': 1000,
        'margin': True,
        'start': datetime_str(2017, 10, 1),
        'end': datetime_str(2017, 10, 31),
        'data_feed': {
            'ohlcv': ['5m', '15m', '1h']
        }
    }
    btest = Backtest(mongo)
    btest.setup(options)
    report = await btest.test()
    del report['trades']

    print('\n================= [Report] =================')
    pp(report)
    print('============================================\n')


run(main)
