from setup import setup, run
setup()

from pprint import pprint
import asyncio

from db import EXMongo
from trading import exchange


loop = asyncio.get_event_loop()


def test_update_wallet(mongo, ex):
    res = loop.run_until_complete(ex.update_wallet())
    pprint(res)


def test_update_ticker(mongo, ex):
    res = loop.run_until_complete(ex.update_ticker())
    pprint(res)


def test_ex_start(mongo, ex):

    async def wait_for_ex_ready(ex):
        while True:
            if ex.is_ready():
                print('ready')
                break
            await asyncio.sleep(2)

    # Start multiple coroutines at the same time
    loop.run_until_complete(asyncio.wait([
        ex.start(log=True),
        wait_for_ex_ready(ex)
    ]))


def test_data_streams(ex):
    loop.run_until_complete(asyncio.wait([
        ex._start_ohlcv_stream(log=True),
        ex._start_orderbook_stream(log=True)
    ]))


def main():
    mongo = EXMongo()
    ex = exchange.bitfinex(mongo)

    # test_update_wallet(mongo, ex)
    # test_update_ticker(mongo, ex)
    # test_ex_start(mongo, ex)
    # test_data_streams(ex)


if __name__ == '__main__':
    run(main)
