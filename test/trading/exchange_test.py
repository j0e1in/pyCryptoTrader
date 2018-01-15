from setup import setup, run
setup()

from datetime import datetime
from pprint import pprint
import asyncio

from db import EXMongo
from trading.exchanges import Bitfinex
from utils import get_project_root, load_keys


async def test_update_wallet(ex):
    print('-- Update wallet --')
    res = await asyncio.gather(ex.update_wallet())
    pprint(res)


async def test_update_ticker(ex):
    print('-- Update ticker --')
    res = await asyncio.gather(ex.update_ticker())
    pprint(res)


async def test_update_markets(ex):
    print('-- Market info --')
    res = await asyncio.gather(ex.update_markets())
    pprint(res)


async def test_ex_start(ex):
    print('-- EX Start --')

    async def wait_for_ex_ready(ex):
        while True:
            if ex.is_ready():
                print('ready')
                break
            await asyncio.sleep(2)

    tasks = ex.start_tasks(log=True)

    # Start multiple coroutines at the same time
    await asyncio.gather(*tasks, wait_for_ex_ready(ex))


async def test_data_streams(ex):
    print('-- Data stream --')
    # await asyncio.gather(asyncio.wait([
    #     ex._start_ohlcv_stream(log=True),
    #     ex._start_orderbook_stream(log=True)
    # ]))
    await asyncio.gather(
        ex._start_ohlcv_stream(log=True),
        ex._start_orderbook_stream(log=True),
    )


async def test_get_orderbook(ex):
    print('-- Get orderbook --')
    res = await asyncio.gather(ex.get_orderbook('BTC/USD'))
    pprint(res)


async def test_fetch_open_orders(ex):
    print('-- Fetch open orders --')
    res = await asyncio.gather(ex.fetch_open_orders())
    pprint(res)


async def test_fetch_closed_orders(ex):
    print('-- Fetch closed orders --')
    res = await asyncio.gather(ex.fetch_closed_orders())
    pprint(res)


async def test_fetch_order(ex):
    print('-- Fetch order --')
    res = await asyncio.gather(ex.fetch_order('7126033276'))
    pprint(res)


async def test_fetch_my_recent_trades(ex):
    print('-- Fetch my recent trades --')
    res = await asyncio.gather(ex.fetch_my_recent_trades('BTC/USD', start=datetime(2018, 1, 15), limit=3))
    pprint(res)


async def test_get_deposit_address(ex):
    print('-- Get deposit address --')
    curr = 'BTC'
    res = await asyncio.gather(ex.get_deposit_address(curr, 'margin'))
    pprint(f"Old {curr} address: {res}")
    res = await asyncio.gather(ex.get_new_deposit_address(curr, 'margin'))
    pprint(f"New {curr} address: {res}")


async def test_create_order(ex):
    print('-- Create order --')
    res = await asyncio.gather(
        ex.create_order('BTC/USD', 'limit', 'sell', amount=0.002, price=99999)
    )
    pprint(res)


async def test_cancel_order(ex):
    print('-- Cancel order --')
    res = await asyncio.gather(ex.cancel_order('134256839'))
    pprint(res)


async def test_fetch_open_positions(ex):
    print('-- Fetch open positions --')
    res = await asyncio.gather(ex.fetch_positions())
    pprint(res)


async def test_cancel_order_multi(ex):
    print('-- Cancel order multi --')
    res = await asyncio.gather(ex.cancel_order_multi(['7178212463', '7178244233']))
    pprint(res)


async def test_cancel_order_all(ex):
    print('-- Cancel order all --')
    res = await asyncio.gather(ex.cancel_order_all())
    pprint(res)


async def test_get_market_price(ex):
    print('-- Get market price --')
    res = await asyncio.gather(ex.get_market_price('BTC/USD'))
    pprint(res)


async def test_update_fees(ex):
    print('-- Trade and withdraw fees --')
    await asyncio.gather(ex.update_trade_fees(), ex.update_withdraw_fees())


async def main():
    mongo = EXMongo()

    key = load_keys(get_project_root() + '/private/keys.json')['bitfinex']
    ex = Bitfinex(mongo, key['apiKey'], key['secret'], verbose=False)

    # await test_ex_start(ex)
    # await test_data_streams(ex)

    # await test_update_wallet(ex)
    # await test_update_ticker(ex)
    # await test_update_markets(ex)

    # await test_get_orderbook(ex)
    # await test_get_deposit_address(ex)
    # await test_get_market_price(ex)

    # await test_create_order(ex)
    # await test_cancel_order(ex)
    # await test_cancel_order_multi(ex)
    # await test_cancel_order_all(ex)

    # await test_fetch_open_orders(ex)
    # await test_fetch_closed_orders(ex) # bug in ccxt
    # await test_fetch_order(ex)
    # await test_fetch_open_positions(ex)
    # await test_fetch_my_recent_trades(ex)

    # await test_update_fees(ex)


if __name__ == '__main__':
    run(main, debug=False)
