from setup import run, setup
setup()

from pprint import pprint as pp

from backtest import Backtest
from mongo import Mongo
from utils import datetime_str


def test_strategy(backtest):
    """ Retrieve data feed which is based on smallest timeframe and
        yield a response: None, ("buy", amount) or ("sell", amount).
    """
    account = backtest.account
    data_feed = backtest.data_feed
    test_info = backtest.test_info

    for data in data_feed['ohlcv']['5m']:
        pass


async def main():
    mongo = Mongo(host='localhost', port=27017)

    options = {
        'strategy': test_strategy,
        'exchange': 'bitfinex',
        'symbol': 'ETH/USD',
        'fund': 10000,
        'start': datetime_str(2017, 10, 1),
        'end': datetime_str(2017, 10, 31),
        'data_feed': {
            'ohlcv': ['1m', '5m', '15m', '1h']
        }
    }
    btest = Backtest(mongo)
    btest.setup(options)
    report = await btest.test()
    pp(report)


run(main)
