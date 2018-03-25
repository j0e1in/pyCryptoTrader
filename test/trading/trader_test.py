from setup import setup, run
setup()

from concurrent.futures import FIRST_COMPLETED
from pprint import pprint
import asyncio

from db import EXMongo
from trading.trader import SingleEXTrader


async def test_trader_start(trader):
    await asyncio.gather(trader.start())


async def test_start_trading(trader):
    await asyncio.gather(trader.start_trading())


async def test_cancel_all_orders(trader):
    print('-- Cancel all orders --')
    res = await asyncio.gather(trader.cancel_all_orders('BTC/USD'))
    pprint(res)


async def test_long(trader):
    print('-- Long --')

    done, pending = await asyncio.wait(
        [
            trader.ex.update_markets(),
            trader.ex.update_trade_fees(),
            trader.long('XRP/USD', confidence=100, type='limit'),
        ],
        return_when=FIRST_COMPLETED)


async def test_short(trader):
    print('-- Short --')

    done, pending = await asyncio.wait(
        [
            trader.ex.update_markets(),
            trader.ex.update_trade_fees(),
            trader.short('BTC/USD', confidence=100, type='limit'),
        ],
        return_when=FIRST_COMPLETED)


async def test_close(trader):
    print('-- Close --')

    done, pending = await asyncio.wait(
        [
            trader.ex.update_markets(),
            trader.close_position('XRP/USD', confidence=100, type='limit'),
            trader.ex.update_trade_fees(),
        ],
        return_when=FIRST_COMPLETED)


async def test_strategy(trader):
    print('-- Strategy --')
    await asyncio.gather(trader.start())


async def test_calc_order_amount(trader):
    print('-- Calc_order_amount --')
    symbol = 'XRP/USD'
    action = 'short'
    side = 'buy' if action == 'long' else 'sell'

    orderbook = await trader.ex.get_orderbook(symbol)
    prices = trader.calc_three_point_prices(orderbook, action)
    await trader.ex.update_markets(once=True)
    await trader.ex.update_trade_fees(once=True)

    res = trader.calc_order_amount(
        symbol,
        'limit',
        side,
        1000,
        orderbook,
        start_price=prices['start_price'],
        end_price=prices['end_price'],
        margin=True,
        scale_order=True)

    pprint(res)


async def test_gen_scale_orders(trader):
    print('-- gen_scale_orders --')
    await trader.ex.update_markets(once=True)
    orders = trader.gen_scale_orders(
        'XRP/USD',
        'limit',
        'sell',
        5184.647812,
        start_price=0.63282312,
        end_price=0.6504553000000001,
        max_order_count=20)
    pprint(orders)

    amount = 0
    value = 0
    for order in orders:
        amount += order['amount']
        value += order['amount'] * order['price']

    print('Total amount:', amount)
    print('Total value:', value)


async def main():
    mongo = EXMongo()
    trader = SingleEXTrader(mongo, 'bitfinex', 'pattern', log=True)

    # await test_trader_start(trader)
    # await test_start_trading(trader)
    # await test_cancel_all_orders(trader)
    # await test_long(trader)
    # await test_short(trader)
    # await test_close(trader)
    # await test_strategy(trader)
    # await test_calc_order_amount(trader)
    # await test_gen_scale_orders(trader)

    await trader.ex.ex.close()


if __name__ == '__main__':
    run(main, debug=False)
