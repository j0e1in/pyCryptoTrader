from setup import run, setup
setup()

from datetime import datetime
from pprint import pprint
import copy
import pickle

from analysis.backtest import Backtest, BacktestRunner
from analysis.strategy import PatternStrategy
from db import EXMongo
from utils import config, print_to_file


async def test_single_period(mongo, market):
    # dt = (datetime(2017, 8, 1), datetime(2018, 3, 5))
    # dt = (datetime(2017, 8, 1), datetime(2017, 12, 10))
    # dt = (datetime(2017, 10, 1), datetime(2018, 2, 20))
    dt = (datetime(2018, 2, 1), datetime(2018, 3, 15))

    _config = copy.deepcopy(config)
    _config['analysis']['exchanges']['bitfinex']['markets'] = [market]
    _config['matplot']['enable'] = False

    options = {
        'strategy': PatternStrategy('bitfinex'),
        'start': dt[0],
        'end': dt[1],
        'custom_config': _config,
    }

    backtest = await Backtest(mongo).init(**options)

    sp = backtest.ohlcvs['bitfinex'][backtest.markets['bitfinex'][0]]['1m'].iloc[0].open
    ep = backtest.ohlcvs['bitfinex'][backtest.markets['bitfinex'][0]]['1m'].iloc[-1].close
    ch = ep / sp if ep >= sp else ((ep / sp) - 1)
    print(f"# {market}\n"
          f"# Starting price: {sp}\n"
          f"# Ending price:   {ep}\n"
          f"# Change(%):      {ch * 100}")

    report = backtest.run()

    print('-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=\n')
    # pprint(report)
    print(market, ':', report['PL(%)'])
    print('\n-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=\n')

    print_to_file(backtest.margin_PLs, '../log/margin_pl.out')
    print_to_file(backtest.trader.wallet_history, '../log/wallet_history.out')
    print_to_file(backtest.trader.order_history['bitfinex'], '../log/order_history.out')

    # Print orders with PL < -30
    # for _, order in hist.items():
    #     # if order['PL'] < -30:
    #     if order['side'] == 'sell':
    #         pprint(order)

    return report

async def test_special_periods_of_markets(mongo):

    markets = [
        "BTC/USD",
        "BCH/USD",
        "ETH/USD",
        "XRP/USD",

        "EOS/USD",
        "LTC/USD",
        "NEO/USD",
        "OMG/USD",

        # "ETC/USD",
        # "DASH/USD",
        # "IOTA/USD",
        # "XMR/USD",
        # "ZEC/USD"
    ]

    total_pl = 0

    for market in markets:
        report = await test_single_period(mongo, market)
        total_pl += report['PL(%)']

    print(f"Total PL(%): {total_pl/len(markets)}")

async def test_special_periods(mongo):
    # periods = [
    #     (datetime(2017, 3, 17), datetime(2017, 3, 19)),
    #     (datetime(2017, 3, 25), datetime(2017, 4, 26)),
    #     (datetime(2017, 5, 15), datetime(2017, 5, 26)),
    #     (datetime(2017, 5, 28), datetime(2017, 6, 14)),
    #     (datetime(2017, 6, 7), datetime(2017, 6, 28)),
    #     (datetime(2017, 6, 18), datetime(2017, 6, 27, 14)),
    #     (datetime(2017, 9, 2), datetime(2017, 9, 15, 11)),
    # ]

    periods = [
        (datetime(2018, 1, 19), datetime(2018, 1, 29)),
    ]

    strategy = PatternStrategy('bitfinex')
    bt_runner = BacktestRunner(mongo, strategy)

    summary = await bt_runner.run_periods(periods)
    pprint(summary)


async def test_random_periods(mongo):
    coin = config['analysis']['exchanges']['bitfinex']['markets'][0].split('/')[0]
    filename = f"{coin}_random_1"

    start = datetime(2017, 3, 5)
    end = datetime(2017, 11, 1)
    period_size_range = (7, 100)

    strategy = PatternStrategy('bitfinex')
    bt_runner = BacktestRunner(mongo, strategy)

    periods = bt_runner.generate_random_periods(start, end, period_size_range, 2000)

    with open(f'../data/{filename}.pkl', 'wb') as f:
        pickle.dump(periods, f)

    pprint(periods)

    summary = await bt_runner.run_periods(periods)
    summary.to_csv(f'../data/{filename}.csv')


async def main():
    mongo = EXMongo()

    await test_special_periods_of_markets(mongo)
    # await test_special_periods(mongo)
    # await test_random_periods(mongo)


if __name__ == '__main__':
    run(main)
