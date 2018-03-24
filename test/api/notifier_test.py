from setup import setup, run
setup()

from pprint import pprint

from api.notifier import Messenger
from db import EXMongo
from trading.trader import SingleEXTrader
from utils import config, load_json

dummy_data = load_json(config['dummy_data_file'])


async def test_notify_open_orders_succ(notifier):
    print('-- notify_open_orders_succ --')
    res = await notifier.notify_open_orders_succ(
        dummy_data['active_orders']['orders'])
    pprint(res)


async def test_notify_open_orders_failed(notifier):
    print('-- notify_open_orders_failed --')
    res = await notifier.notify_open_orders_failed(
        dummy_data['active_orders']['orders'])
    pprint(res)


async def test_notify_position_danger(notifier):
    print('-- notify_position_danger --')
    res = await notifier.notify_position_danger(
        dummy_data['active_positions']['positions'])
    pprint(res)


async def test_notify_position_large_pl(notifier):
    print('-- notify_position_large_pl --')
    res = await notifier.notify_position_large_pl(
        dummy_data['active_positions']['positions'])
    pprint(res)


async def test_notify_log(notifier):
    print('-- notify_log --')
    res = await notifier.notify_log('warning', 'Test warning')
    pprint(res)


async def test_notify_start(notifier):
    print('-- notify_start --')
    res = await notifier.notify_start()
    pprint(res)


async def test_notify_msg(notifier):
    print('-- notify_msg --')
    res = await notifier.notify_msg("hello")
    pprint(res)


async def main():

    mongo = EXMongo()

    trader = SingleEXTrader(mongo, 'bitfinex', 'pattern',
                            disable_trading=True, log=True)

    notifier = Messenger(trader, ssl=True)

    # await test_notify_open_orders_succ(notifier)
    # await test_notify_open_orders_failed(notifier)
    # await test_notify_position_danger(notifier)
    # await test_notify_position_large_pl(notifier)
    # await test_notify_log(notifier)
    # await test_notify_start(notifier)
    # await test_notify_msg(notifier)

    await notifier.close()
    await trader.ex.ex.close()


if __name__ == "__main__":
    run(main)