from setup import setup, run
setup()

from pprint import pprint
import asyncio

from db import EXMongo
from trading.exchanges import Bitfinex
from trading.trader import SingleEXTrader
from utils import get_project_root, load_keys

loop = asyncio.get_event_loop()


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
    await asyncio.gather(
        trader.long('BTC/USD', 100, type='limit'),
        trader.ex.update_trade_fees()
    )


async def test_short(trader):
    print('-- Short --')
    await asyncio.gather(
        trader.short('BTC/USD', 100, type='limit'),
        trader.ex.update_trade_fees()
    )


async def main():
    mongo = EXMongo()
    trader = SingleEXTrader(mongo, 'bitfinex', None)

    # await asyncio.gather(test_trader_start(trader))
    # await asyncio.gather(test_start_trading(trader))
    # await asyncio.gather(test_cancel_all_orders(trader))
    await asyncio.gather(test_long(trader))
    await asyncio.gather(test_short(trader))


if __name__ == '__main__':
    run(main, debug=False)
