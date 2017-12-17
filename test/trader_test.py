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
timeframes = config['trader']['exchanges']['bitfinex']['timeframes']
margin_rate = config['trader']['margin_rate']

start = datetime(2017, 1, 1)
end = datetime(2017, 1, 2)


async def _feed_ohlcv(trader, mongo):
    ohlcvs = {}
    ohlcvs[ex_name(exchange)] = await mongo.get_ohlcvs_of_symbols(exchange, symbols, timeframes, start, end)
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


async def test_normarl_order_execution(order_type, trader, mongo):
    ohlcvs = {}
    ohlcvs[ex_name(exchange)] = await mongo.get_ohlcvs_of_symbols(exchange, symbols, timeframes, start, end)

    trades = {}
    trades[ex_name(exchange)] = await mongo.get_trades_of_symbols(exchange, symbols, start, end)
    buy_time = datetime(2017, 1, 1, 7, 33)
    sell_time = datetime(2017, 1, 1, 21, 45)

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
            if order_type == 'limit':
                order_type = 'limit'
                price = trader.cur_price(ex, market)
                amount = trader.wallet[ex]['USD'] * 0.9 / price
            else:
                order_type = 'market'
                amount = trader.wallet[ex]['USD'] * 0.9 / trader.cur_price(ex, market)
                price = None

            order = trader.generate_order(ex, market, side, order_type, amount, price)
            pprint(order)
            trader.open(order)
            bought = True

        if bought and not sold and cur_time >= sell_time:
            side = 'sell'
            if order_type == 'limit':
                price = trader.cur_price(ex, market)
            else:
                price = None
            amount = trader.wallet[ex]['BTC']
            order = trader.generate_order(ex, market, side, order_type, amount, price)
            pprint(order)
            trader.open(order)
            sold = True

    pprint(trader.wallet)
    pprint(trader.order_records)


async def test_margin_order_execution(order_type, trader, mongo):
    ohlcvs = {}
    ohlcvs[ex_name(exchange)] = await mongo.get_ohlcvs_of_symbols(exchange, symbols, timeframes, start, end)

    trades = {}
    trades[ex_name(exchange)] = await mongo.get_trades_of_symbols(exchange, symbols, start, end)
    buy_time = datetime(2017, 1, 1, 12, 33)
    sell_time = datetime(2017, 1, 1, 23, 45)

    bought = False
    sold = False
    order = None

    cur_time = trader.timer.now()
    while cur_time < end:
        cur_time = trader.timer.now()
        next_time = trader.timer.next()
        trader.feed_data(ohlcvs, trades, cur_time, next_time)

        if not bought and cur_time >= buy_time:
            ex = 'bitfinex'
            market = 'BTC/USD'
            side = 'buy'
            if order_type == 'limit':
                order_type = 'limit'
                price = trader.cur_price(ex, market)
                amount = trader.wallet[ex]['USD'] * 0.9 / price * margin_rate
            else:
                order_type = 'market'
                amount = trader.wallet[ex]['USD'] * 0.9 / trader.cur_price(ex, market) * margin_rate
                price = None

            order = trader.generate_order(ex, market, side, order_type, amount, price, margin=True)
            pprint(order)
            order = trader.open(order)
            bought = True

        if trader.is_position_open(order)\
        and not sold and cur_time >= sell_time:
            trader.close_position(order)
            sold = True

    pprint(trader.wallet)
    pprint(trader.order_records)



async def main():
    timer = Timer(start, timer_interval)
    trader = SimulatedTrader(timer)
    mongo = EXMongo()

    print('------------------------------')
    await test_feed_ohlcv_trades(trader, mongo)
    print('------------------------------')
    trader.reset()
    await test_normarl_order_execution('limit', trader, mongo)
    print('------------------------------')
    trader.reset()
    await test_normarl_order_execution('market', trader, mongo)
    print('------------------------------')
    trader.reset()
    await test_margin_order_execution('limit', trader, mongo)
    print('------------------------------')
    trader.reset()
    await test_margin_order_execution('market', trader, mongo)
    print('------------------------------')

run(main)
