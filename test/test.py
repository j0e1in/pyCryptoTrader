import asyncio
import chromalog
import logging
import time


def setup():
    import sys
    sys.path.append('../src')

    chromalog.basicConfig(level=logging.DEBUG,
                          format='%(asctime)s | `%(funcName)s` | %(filename)s | %(levelname)s : %(message)s')


def run_test(func, *args, **kwargs):

    loop = asyncio.get_event_loop()

    s = time.time()
    loop.run_until_complete(func(*args, **kwargs))
    e = time.time()

    print('========================')
    print('time:', e-s)
    print('========================')

    loop.run_until_complete(asyncio.sleep(0.5))


