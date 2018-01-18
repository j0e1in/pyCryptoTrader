import asyncio
import chromalog
import logging
import time
import os
import sys

log_fmt = '%(asctime)s | %(filename)s | %(funcName)s | %(levelname)5s | %(message)s'

file_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(file_dir)


def setup():

    os.chdir(root_dir + '/lib')
    sys.path.append('.')

    chromalog.basicConfig(level=logging.DEBUG,
                          stream=sys.stdout,
                          format=log_fmt)


def run(func, debug=False, log_file=None, *args, **kwargs):

    if log_file:
        log_file = f"{root_dir}/log/{log_file}"

        # Add file handler to logger (stdout is already set)
        fh = logging.FileHandler(log_file, mode='w')
        fh.setFormatter(logging.Formatter(log_fmt))
        logging.getLogger().addHandler(fh)

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


