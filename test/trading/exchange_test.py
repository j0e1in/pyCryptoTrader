from setup import setup, run
setup()

from pprint import pprint
import asyncio

from db import EXMongo
from trading.exchange import Bitfinex
from utils import get_project_root, load_keys

loop = asyncio.get_event_loop()


def test_update_wallet(ex):
    print('-- Update wallet --')
    res = loop.run_until_complete(ex.update_wallet())
    pprint(res)


def test_update_ticker(ex):
    print('-- Update ticker --')
    res = loop.run_until_complete(ex.update_ticker())
    pprint(res)


def test_update_markets_info(ex):
    print('-- Market info --')
    res = loop.run_until_complete(ex.update_markets_info())
    pprint(res)


def test_ex_start(ex):
    print('-- EX Start --')
    async def wait_for_ex_ready(ex):
        while True:
            if ex.is_ready():
                print('ready')
                break
            await asyncio.sleep(2)

    tasks = ex.start_tasks(log=True)

    # Start multiple coroutines at the same time
    loop.run_until_complete(asyncio.wait([
        *tasks,
        wait_for_ex_ready(ex)
    ]))


def test_data_streams(ex):
    print('-- Data stream --')
    loop.run_until_complete(asyncio.wait([
        ex._start_ohlcv_stream(log=True),
        ex._start_orderbook_stream(log=True)
    ]))


def test_get_orderbook(ex):
    print('-- Get orderbook --')
    res = loop.run_until_complete(ex.get_orderbook('BTC/USD'))
    pprint(res)


def test_fetch_open_orders(ex):
    print('-- Fetch open orders --')
    res = loop.run_until_complete(ex.fetch_open_orders())
    pprint(res)


def test_fetch_order(ex):
    print('-- Fetch order --')
    res = loop.run_until_complete(ex.fetch_order('7126033276'))
    pprint(res)


def test_fetch_my_trades(ex):
    print('-- Fetch my trades --')
    res = loop.run_until_complete(ex.fetch_my_trades('BTC/USD'))
    pprint(res)


def test_get_deposit_address(ex):
    print('-- Get deposit address --')
    curr = 'BTC'
    res = loop.run_until_complete(ex.get_deposit_address(curr, 'margin'))
    pprint(f"Old {curr} address: {res}")
    res = loop.run_until_complete(ex.get_new_deposit_address(curr, 'margin'))
    pprint(f"New {curr} address: {res}")


def test_create_order(ex):
    print('-- Create order --')
    res = loop.run_until_complete(
        ex.create_order('BTC/USD', 'limit', 'sell', amount=0.0035, price=99999)
    )
    pprint(res)
    return res['id']


def test_cancel_order(ex):
    print('-- Cancel order --')
    res = loop.run_until_complete(ex.cancel_order('134256839'))
    pprint(res)


def test_fetch_open_positions(ex):
    print('-- Fetch open positions --')
    res = loop.run_until_complete(ex.fetch_positions('7178212463'))
    pprint(res)


def test_cancel_order_multi(ex):
    print('-- Cancel order multi --')
    res = loop.run_until_complete(ex.cancel_order_multi(['7178212463', '7178244233']))
    pprint(res)


def test_cancel_order_all(ex):
    print('-- Cancel order all --')
    res = loop.run_until_complete(ex.cancel_order_all())
    pprint(res)


def main():
    mongo = EXMongo()

    key = load_keys(get_project_root() + '/private/keys.json')['bitfinex']
    ex = Bitfinex(mongo, key['apiKey'], key['secret'], verbose=False)

    # test_update_wallet(ex)
    # test_update_ticker(ex)
    # test_update_markets_info(ex)

    # test_ex_start(ex)
    # test_data_streams(ex)
    # test_get_orderbook(ex)
    # test_get_deposit_address(ex)

    # test_fetch_open_orders(ex)
    # test_fetch_order(ex)
    # test_fetch_my_trades(ex)
    # test_fetch_open_positions(ex)

    # test_create_order(ex)
    test_cancel_order(ex)
    # test_cancel_order_multi(ex)
    # test_cancel_order_all(ex)


if __name__ == '__main__':
    run(main)
