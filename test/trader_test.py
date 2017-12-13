from setup import run, setup
setup()

from pprint import pprint

from db import EXMongo
from trader import SimulatedTrader
from utils import Timer, config, utc_ts, init_ccxt_exchange, config, ex_name


timer_interval = config['backtest']['base_timeframe']

exchange = init_ccxt_exchange('bitfinex2')
markets = ['BTC/USD', 'ETH/USD']

start = utc_ts(2017, 1, 1)
end = utc_ts(2017, 1, 2)


def test_init_account(trader):
    fund = {'bitfinex': {'USD': 1000}}
    trader.init_account()
    pprint(trader.account)


async def _feed_ohlcv(trader, mongo):
    ohlcvs = {}
    ohlcvs[ex_name(exchange)] = await mongo.get_ohlcv_of_symbols(exchange, markets, start, end)
    trader.feed_ohlcv(ohlcvs)


async def _feed_trades(trader, mongo):
    trades = {}
    fields_condition = {'symbol': 0}
    trades[ex_name(exchange)] = await mongo.get_trades_of_symbols(exchange, markets, start, end,
                                                                  fields_condition=fields_condition)
    trader.feed_trades(trades)


async def test_feed_ohlcv_trades(trader, mongo):
    await _feed_ohlcv(trader, mongo)
    await _feed_trades(trader, mongo)

    pprint(trader.ohlcvs['bitfinex']['BTC/USD']['1m'])
    pprint(trader.trades['bitfinex']['BTC/USD'])


async def test_normarl_limit_order_execution(trader, mongo):
    ohlcvs = {}
    ohlcvs[ex_name(exchange)] = await mongo.get_ohlcv_of_symbols(exchange, markets, start, end)

    trades = {}
    fields_condition = {'symbol': 0}
    trades[ex_name(exchange)] = await mongo.get_trades_of_symbols(exchange, markets, start, end,
                                                                  fields_condition=fields_condition)
    buy_time = utc_ts(2017, 1, 1, 12)
    sell_time = utc_ts(2017, 1, 1, 18)

    trader.feed_data(buy_time, sell_time, ohlcvs, trades)
    print(trader.trades['bitfinex']['BTC/USD'])


async def main():
    start = utc_ts(2017, 1, 1)
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
