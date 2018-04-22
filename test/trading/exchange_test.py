from setup import run


from datetime import datetime
from pprint import pprint
import asyncio

from db import EXMongo
from trading.exchanges import Bitfinex
from utils import get_project_root, load_keys, config


async def test_update_wallet(ex):
    print('-- Update wallet --')
    res = await ex.update_wallet()
    pprint(res)


async def test_update_ticker(ex):
    print('-- Update ticker --')
    res = await ex.update_ticker()
    pprint(res)


async def test_update_markets(ex):
    print('-- Market info --')
    res = await ex.update_markets()
    pprint(res)


async def test_ex_start(ex):
    print('-- EX Start --')

    async def wait_for_ex_ready(ex):
        while True:
            if ex.is_ready():
                print('ready')
                break
            await asyncio.sleep(2)

    tasks = ex.start_tasks()

    # Start multiple coroutines at the same time
    await asyncio.gather(*tasks, wait_for_ex_ready(ex))


async def test_data_streams(ex):
    print('-- Data stream --')
    # await asyncio.gather(asyncio.wait([
    #     ex._start_ohlcv_stream(),
    #     ex._start_orderbook_stream()
    # ]))
    await asyncio.gather(
        ex._start_ohlcv_stream(),
        ex._start_orderbook_stream(),
    )


async def test_get_orderbook(ex):
    print('-- Get orderbook --')
    res = await ex.get_orderbook('BTC/USD')
    pprint(res)


async def test_fetch_open_orders(ex):
    print('-- Fetch open orders --')
    res = await ex.fetch_open_orders()
    pprint(res)


async def test_fetch_order(ex):
    print('-- Fetch order --')
    res = await ex.fetch_order('7126033276')
    pprint(res)


async def test_fetch_my_recent_trades(ex):
    print('-- Fetch my recent trades --')
    res = await ex.fetch_my_recent_trades('BTC/USD', start=datetime(2018, 1, 15), limit=3)
    pprint(res)


async def test_update_my_trades(ex):
    print('-- Update my trades --')
    res = await ex.update_my_trades()


async def test_get_deposit_address(ex):
    print('-- Get deposit address --')
    curr = 'BTC'
    res = await ex.get_deposit_address(curr, 'margin')
    pprint(f"Old {curr} address: {res}")
    res = await ex.get_new_deposit_address(curr, 'margin')
    pprint(f"New {curr} address: {res}")


async def test_create_order(ex):
    print('-- Create order --')
    res = await ex.create_order('BTC/USD', 'limit', 'sell', amount=0.002, price=99999)
    pprint(res)


async def test_create_order_multi(ex):
    print('-- Create order multi --')

    orders = [
        {
            "symbol": 'BTC/USD',
            "type": 'limit',
            "side": 'sell',
            "amount": '0.002',
            "price": 99999,
        },
        {
            "symbol": 'BTC/USD',
            "type": 'limit',
            "side": 'sell',
            "amount": '0.002',
            "price": 88888,
        },
    ]
    res = await ex.create_order_multi(orders)
    pprint(res)


async def test_cancel_order(ex):
    print('-- Cancel order --')
    res = await ex.cancel_order('134256839')
    pprint(res)


async def test_fetch_open_positions(ex):
    print('-- Fetch open positions --')
    res = await ex.fetch_positions()
    pprint(res)


async def test_cancel_order_multi(ex):
    print('-- Cancel order multi --')
    res = await ex.cancel_order_multi(['7178212463', '7178244233'])
    pprint(res)


async def test_cancel_order_all(ex):
    print('-- Cancel order all --')
    res = await ex.cancel_order_all()
    pprint(res)


async def test_close_position(ex):
    print('-- Close position --')
    res = await ex.close_position('XRP/USD')
    pprint(res)


async def test_get_market_price(ex):
    print('-- Get market price --')
    res = await ex.get_market_price('BTC/USD')
    pprint(res)


async def test_update_fees(ex):
    print('-- Trade and withdraw fees --')
    await asyncio.gather(ex.update_trade_fees(), ex.update_withdraw_fees())


async def test_transfer_funds(ex):
    print('-- Transfer funds --')
    res = await ex.update_wallet()
    res = await ex.transfer_funds('USD', res['USD']['margin']*1.1, 'margin', 'funding')
    pprint(res)


async def test_calc_trade_fee(ex):
    print('-- Calculate trade fee --')
    res = await ex.calc_trade_fee(
        datetime(2017, 12, 1),
        datetime(2018, 2, 1)
    )
    pprint(res)


async def test_calc_order_value(ex):
    print('-- Calculate order value --')
    res = await ex.calc_order_value()
    pprint(res)


async def test_calc_all_position_value(ex):
    print('-- Calculate position value --')
    res = await ex.calc_all_position_value()
    pprint(res)


async def main():
    mongo = EXMongo()

    ex_id = 'bitfinex'
    uid = config['uid']
    key = load_keys()[uid][ex_id]
    ex = Bitfinex(mongo, uid=uid, apikey=key['apiKey'], secret=key['secret'], ccxt_verbose=False, log=True)
    await ex.ex.load_markets()

    # await test_ex_start(ex)
    # await test_data_streams(ex)

    # await test_update_wallet(ex)
    # await test_update_ticker(ex)
    # await test_update_markets(ex)

    # await test_get_orderbook(ex)
    # await test_get_deposit_address(ex)
    # await test_get_market_price(ex)

    # await test_create_order(ex)
    # await test_create_order_multi(ex)
    # await test_cancel_order(ex)
    # await test_cancel_order_multi(ex)
    # await test_cancel_order_all(ex)
    # await test_close_position(ex)

    # await test_fetch_open_orders(ex)
    # await test_fetch_order(ex)
    # await test_fetch_open_positions(ex)
    # await test_fetch_my_recent_trades(ex)
    # await test_update_my_trades(ex)
    # await test_transfer_funds(ex)
    # await test_calc_trade_fee(ex)
    # await test_calc_order_value(ex)
    # await test_calc_all_position_value(ex)

    # await test_update_fees(ex)

    await ex.ex.close()


if __name__ == '__main__':
    run(main, debug=False)
