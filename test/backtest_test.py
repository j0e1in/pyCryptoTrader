from setup import run, setup
setup()

from pprint import pprint as pp

from backtest import Backtest
from db import EXMongo
from utils import exchange_timestamp


def test_strategy(backtest):
    account = backtest.account
    data_feed = backtest.data_feed
    test_info = backtest.test_info
    open_orders = []

    i = 0
    long_short = "long"
    for data in data_feed['ohlcv']['5m']:
        i += 1
        if i % 1000 == 0:
            if len(open_orders) > 0:
                backtest.close_all_orders(data['timestamp'])

            price = backtest.get_foreward_price(data['timestamp'], long_short, margin=test_info['margin'])
            amount = account['qoute_balance'] * 0.9 / price
            succ, order_id = backtest.open_order(long_short, data['timestamp'], amount)
            if succ:
                open_orders.append(order_id)
                long_short = "short" if long_short == "long" else "long"


async def main():
    mongo = EXMongo(host='localhost', port=27017)

    options = {
        'strategy': test_strategy,
        'exchange': 'bitfinex',
        'symbol': 'ETH/USD',
        'fund': 1000,
        'margin': True,
        'start': exchange_timestamp(2017, 10, 1),
        'end': exchange_timestamp(2017, 10, 31),
        'data_feed': {
            'ohlcv': ['5m', '15m', '1h']
        }
    }
    btest = Backtest(mongo)
    await btest.setup(options)
    report = btest.test()
    del report['trades']

    print('\n================= [Report] =================')
    pp(report)
    print('============================================\n')


run(main)
