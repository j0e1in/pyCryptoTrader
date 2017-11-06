from test import run, setup
setup()

from pprint import pprint as pp
import ccxt.async as ccxt
import asyncio
import motor.motor_asyncio as motor
from asyncio import ensure_future

from utils import combine, get_keys, get_constants, datetime_str, ms_sec
from hist_data import fetch_ohlcv_handler

consts = get_constants()


async def main():
    pass


run(main)
