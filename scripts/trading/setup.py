import asyncio
import chromalog
import logging
import time
import os
import sys

try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass

file_dir = os.path.dirname(os.path.abspath(__file__))
file_dir = os.path.dirname(file_dir)
root_dir = os.path.dirname(file_dir)

os.chdir(root_dir + '/lib')
sys.path.append('.')

from utils import config, log_config, register_logging_file_handler


def run(func, debug=False, log_file=None, *args, **kwargs):

    if log_file:
        log_file = f"{root_dir}/log/{log_file}"
        register_logging_file_handler(log_file, log_config)

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
