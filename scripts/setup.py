import asyncio
import chromalog
import logging
import time


def setup():
    import sys
    sys.path.append('../lib')

    chromalog.basicConfig(level=logging.DEBUG,
                          stream=sys.stdout,
                          format='%(asctime)s | %(filename)s | %(funcName)15s | %(levelname)13s | %(message)s')


def run(func, *args, **kwargs):

    loop = asyncio.get_event_loop()

    s = time.time()
    loop.run_until_complete(func(*args, **kwargs))
    e = time.time()

    print('========================')
    print('time:', e-s)
    print('========================')

    loop.run_until_complete(asyncio.sleep(0.5))


