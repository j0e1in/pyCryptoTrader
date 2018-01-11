from setup import run, setup
setup()

import asyncio

from db import EXMongo
from trading.exchange import EX


loop = asyncio.get_event_loop()


async def wait_for_ex_ready(ex):
    while True:
        if ex.is_ready():
            print('ready')
            break
        await asyncio.sleep(2)


def test_start_ohlcv_stream(mongo):
    ex = EX(mongo, 'bitfinex2')

    loop.run_until_complete(
        asyncio.wait([
            ex.start(),
            wait_for_ex_ready(ex)
    ]))


def main():
    mongo = EXMongo()

    test_start_ohlcv_stream(mongo)


if __name__ == '__main__':
    main()
