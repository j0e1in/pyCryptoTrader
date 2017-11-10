from setup import setup, run
setup()

from pprint import pprint as pp

from strategy import PatternStrategy
from mongo import Mongo
from utils import datetime_str
import strategy


async def main():
    mongo = Mongo(host='localhost', port=27017)

    options = {
        'strategy': None,
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

    strate = PatternStrategy(mongo)
    await trate.setup(options)
    report = strate.test()

    del report['trades']

    print('\n================= [Report] =================')
    pp(report)
    print('============================================\n')


run(main)

