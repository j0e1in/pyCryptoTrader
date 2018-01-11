from setup import run, setup
setup()

from copy import deepcopy
from datetime import datetime
from pprint import pprint
import logging

from analysis.backtest import Backtest
from analysis.backtest_trader import SimulatedTrader
from db import EXMongo
from utils import Timer, config, init_ccxt_exchange, ex_name, ms_dt

logger = logging.getLogger()

MARKET = config['analysis']['exchanges']['bitfinex']['markets'][0]

timer_interval = config['backtest']['base_timeframe']
exchange = init_ccxt_exchange('bitfinex')
symbols = config['analysis']['exchanges']['bitfinex']['markets']
timeframes = config['analysis']['exchanges']['bitfinex']['timeframes']
margin_rate = config['analysis']['margin_rate']

start = datetime(2017, 1, 1)
end = datetime(2017, 1, 5)


async def _feed_ohlcv(trader, mongo):
    ohlcvs = {}
    ohlcvs[ex_name(exchange)] = await mongo.get_ohlcvs_of_symbols(exchange, symbols, timeframes, start, end)
    trader.feed_ohlcv(ohlcvs, end)


async def _feed_trades(trader, mongo):
    trades = {}
    trades[ex_name(exchange)] = await mongo.get_trades_of_symbols(exchange, symbols, start, end)
    trader.feed_trade(trades, end)


async def test_feed_ohlcv_trades(trader, mongo):
    await _feed_ohlcv(trader, mongo)
    await _feed_trades(trader, mongo)

    pprint(trader.ohlcvs['bitfinex'])
    pprint(trader.trades['bitfinex'])


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

        trader.feed_data(next_time, ohlcvs, trades)
        trader.tick()

        if not bought and cur_time >= buy_time:
            ex = 'bitfinex'
            market = MARKET
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

            curr = config['analysis']['exchanges']['bitfinex']['markets'][0].split('/')[0]
            amount = trader.wallet[ex][curr]
            order = trader.generate_order(ex, market, side, order_type, amount, price)
            pprint(order)
            trader.open(order)
            sold = True

    pprint(trader.wallet)
    pprint(trader.order_records)


async def test_margin_order_execution(order_type, trader, mongo):
    ohlcvs = {}
    ohlcvs[ex_name(exchange)] = await mongo.get_ohlcvs_of_symbols(exchange, symbols, timeframes, start, end)

    buy_time = datetime(2017, 1, 1, 12, 33)
    sell_time = datetime(2017, 1, 1, 23, 45)

    bought = False
    sold = False
    order = None

    cur_time = trader.timer.now()
    while cur_time < end:
        cur_time = trader.timer.now()
        next_time = trader.timer.next()
        trader.feed_data(next_time, ohlcvs)
        trader.tick()

        if not bought and cur_time >= buy_time:
            ex = 'bitfinex'
            market = MARKET
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


# TODO: Finish verify trader's trading algorithm
# def verify_trading_algorithm():
#     start = datetime(2017, 10, 10)
#     end = datetime(2017, 10, 30)
#     exchange = 'bitfinex'
#     strategy = PatternStrategy(exchange)

#     options = {
#         'strategy': strategy,
#         'start': start,
#         'end': end
#     }
#     backtest = await Backtest(mongo).init(**options)
#     report = backtest.run()

#     wallet = deepcopy(report['initial_wallet'])

#     cur = start
#     while cur <= end:

#     for order in backtest.order_history.values():
#         if order['margin']:
#             curr = order['curr']

#             if wallet[order['ex']][curr] < order['cost']:
#                 logger.warn(f"Cost exceeds current balance. \n=> {wallet}\n=> {order}")

#             wallet[order['ex']][curr] -= order['cost']


#         else:
#             if order['side'] == 'buy':
#                 curr = order['curr']
#                 opp_curr = backtest.trader.opposite_currency(order, curr)

#                 if wallet[order['ex']][curr] < order['cost']:
#                     logger.warn(f"Cost exceeds current balance. \n=> {wallet}\n=> {order}")

#                 wallet[order['ex']][curr] -= order['cost']
#                 wallet[order['ex']][opp_curr] += order['amount']
#             else:
#                 curr = order['curr']
#                 opp_curr = backtest.trader.opposite_currency(order, curr)

#                 if wallet[order['ex']][curr] < order['cost']:
#                     logger.warn(f"Cost exceeds current balance. \n=> {wallet}\n=> {order}")

#                 wallet[order['ex']][curr] -= order['cost']
#                 wallet[order['ex']][opp_curr] += order['amount'] * order['open_price']



async def main():
    mongo = EXMongo()
    timer = Timer(start, timer_interval)
    trader = SimulatedTrader(timer)

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


if __name__ == '__main__':
    run(main)

