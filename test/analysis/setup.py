import asyncio
import chromalog
import logging
import time

def setup():
    import os
    import sys

    file_dir = os.path.dirname(os.path.abspath(__file__))
    file_dir = os.path.dirname(file_dir)
    file_dir = os.path.dirname(file_dir)

    os.chdir(file_dir + '/lib')
    sys.path.append('.')

    chromalog.basicConfig(level=logging.DEBUG,
                          stream=sys.stdout,
                          format='%(asctime)s | %(filename)s | %(funcName)s | %(levelname)5s | %(message)s')


def run(func, debug=False, *args, **kwargs):

    if asyncio.iscoroutinefunction(func):
        loop = asyncio.get_event_loop()
        loop.set_debug(debug)

        s = time.time()
        loop.run_until_complete(func(*args, **kwargs))
        e = time.time()

        print('========================')
        print('time:', e-s)
        print('========================')

        loop.run_until_complete(asyncio.sleep(0.5))

    else:
        s = time.time()
        func(*args, **kwargs)
        e = time.time()

        print('========================')
        print('time:', e-s)
        print('========================')


