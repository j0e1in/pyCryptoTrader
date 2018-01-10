from setup import run, setup
setup()

from datetime import datetime
import pandas as pd

from analysis.plot import Plot
from analysis.backtest_trader import SimulatedTrader
from db import EXMongo
from utils import config, Timer
from backtest_trader_test import test_normarl_order_execution,\
                                 test_margin_order_execution,\
                                 start, end, timer_interval

exchange = 'bitfinex'
symbol = config['trader']['exchanges']['bitfinex']['markets'][0]
timeframe = '30m'


async def test_plot_ohlc(mongo):
    plot = Plot()

    ohlcv = await mongo.get_ohlcv(exchange, symbol, timeframe, start, end)
    plot.plot_ohlc(ohlcv)
    plot.show()


async def test_plot_order_annotation(mongo, trader):
    await test_normarl_order_execution('limit', trader, mongo)
    normal_orders = trader.get_hist_normal_orders(exchange, symbol)

    plot = Plot()
    ohlcv = trader.ohlcvs[exchange][symbol][timeframe]
    plot.plot_ohlc(ohlcv)
    plot.plot_order_annotation(normal_orders, ohlcv)
    plot.show()


async def main():
    mongo = EXMongo()
    timer = Timer(start, timer_interval)
    trader = SimulatedTrader(timer)

    # await test_plot_ohlc(mongo)
    await test_plot_order_annotation(mongo, trader)


if __name__ == '__main__':
    run(main)
