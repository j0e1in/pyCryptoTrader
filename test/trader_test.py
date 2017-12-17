from setup import run, setup
setup()

from pprint import pprint
from datetime import datetime

from db import EXMongo
from trader import SimulatedTrader
from utils import Timer, config, init_ccxt_exchange, config, ex_name, ms_dt


timer_interval = config['backtest']['base_timeframe']

exchange = init_ccxt_exchange('bitfinex2')
symbols = config['trader']['exchanges']['bitfinex']['markets']

start = datetime(2017, 1, 1)
end = datetime(2017, 1, 2)


def test_init_account(trader):
    fund = {'bitfinex': {'USD': 1000}}
    trader.init_account()
    pprint(trader.account)


async def _feed_ohlcv(trader, mongo):
    ohlcvs = {}
    ohlcvs[ex_name(exchange)] = await mongo.get_ohlcv_of_symbols(exchange, symbols, start, end)
    trader.feed_ohlcv(ohlcvs)


async def _feed_trades(trader, mongo):
    trades = {}
    trades[ex_name(exchange)] = await mongo.get_trades_of_symbols(exchange, symbols, start, end)
    trader.feed_trades(trades)


async def test_feed_ohlcv_trades(trader, mongo):
    await _feed_ohlcv(trader, mongo)
    await _feed_trades(trader, mongo)

    pprint(trader.ohlcvs['bitfinex']['BTC/USD']['1m'])
    pprint(trader.trades['bitfinex']['BTC/USD'])


async def test_normarl_limit_order_execution(trader, mongo):
    ohlcvs = {}
    ohlcvs[ex_name(exchange)] = await mongo.get_ohlcv_of_symbols(exchange, symbols, start, end)

    trades = {}
    trades[ex_name(exchange)] = await mongo.get_trades_of_symbols(exchange, symbols, start, end)
    buy_time = datetime(2017, 1, 1, 11)
    sell_time = datetime(2017, 1, 1, 18)

    bought = False
    sold = False

    cur_time = trader.timer.now()
    while cur_time < end:
        cur_time = trader.timer.now()
        next_time = trader.timer.next()
        trader.feed_data(ohlcvs, trades, cur_time, next_time)

        if not bought and cur_time >= buy_time:
            ex = 'bitfinex'
            market = 'BTC/USD'
            side = 'buy'
            order_type = 'limit'
            price = trader.cur_price(ex, market)
            amount = trader.wallet[ex]['USD']*0.9/price
            order = trader.generate_order(ex, market, side, order_type, amount, price)
            trader.open(order)
            bought = True

        if bought and not sold and cur_time >= sell_time:
            side = 'sell'
            price = trader.cur_price(ex, market)
            amount = trader.wallet[ex]['BTC']
            order = trader.generate_order(ex, market, side, order_type, amount, price)
            trader.open(order)
            sold = True

    pprint(trader.account)


async def main():
    timer = Timer(start, timer_interval)
    trader = SimulatedTrader(timer)
    mongo = EXMongo()

    print('------------------------------')
    # test_init_account(trader)
    print('------------------------------')
    # await test_feed_ohlcv_trades(trader, mongo)
    print('------------------------------')
    await test_normarl_limit_order_execution(trader, mongo)
    print('------------------------------')


run(main)
