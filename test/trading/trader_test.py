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
            trader.long('XRP/USD', confidence=100, type='limit'),
            trader.ex.update_trade_fees(),
        ],
        return_when=FIRST_COMPLETED)


async def test_short(trader):
    print('-- Short --')

    done, pending = await asyncio.wait(
        [
            trader.ex.update_markets(),
            trader.short('XRP/USD', confidence=100, type='limit'),
            trader.ex.update_trade_fees(),
        ],
        return_when=FIRST_COMPLETED)


async def test_strategy(trader):
    print('-- Strategy --')
    await asyncio.gather(trader.start())


async def test_gen_scale_orders(trader):
    print('-- gen_scale_orders --')
    await trader.ex.update_markets()
    orders = trader.gen_scale_orders(trader.ex.exname, 'limit', 'buy', 100,
                                     start_price=1000,
                                     end_price=900,
                                     order_count=10)
    pprint(orders)

    amount = 0
    for order in orders:
        amount += order['amount']

    print('Total amount:', amount)


async def main():
    mongo = EXMongo()
    trader = SingleEXTrader(mongo, 'bitfinex', 'pattern', log=True)

    # await asyncio.gather(test_trader_start(trader))
    # await asyncio.gather(test_start_trading(trader))
    # await asyncio.gather(test_cancel_all_orders(trader))
    # await asyncio.gather(test_long(trader))
    # await asyncio.gather(test_short(trader))
    # await asyncio.gather(test_strategy(trader))
    # await test_gen_scale_orders(trader)

    await trader.ex.ex.close()


if __name__ == '__main__':
    run(main, debug=False)
