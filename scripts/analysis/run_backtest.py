from setup import run


from datetime import datetime
from pprint import pprint

import argparse
import copy
import pickle

from analysis.backtest import Backtest, BacktestRunner, get_data_feed
from analysis.strategy import PatternStrategy
from db import EXMongo
from utils import config, print_to_file


async def test_single_period(mongo, market, plot, log_signal):

    # dt = (datetime(2017, 8, 1), datetime(2018, 3, 5))
    dt = (datetime(2018, 3, 1), datetime(2018, 4, 5))
    ex = 'bitfinex'

    _config = copy.deepcopy(config)
    _config['analysis']['exchanges'][ex]['markets'] = [market]
    _config['analysis']['log_signal'] = log_signal

    strategy = PatternStrategy(ex, custom_config=_config)
    params = await mongo.get_params(ex)

    params[market] = {
        "trade_portion": 0.5,
        "stop_loss_percent": 0.06,
        "stop_profit_percent": 0.02,
        "ind_conf": 100,

        "stochrsi_length": 18,
        "stoch_length": 10,
        "stochrsi_slowk_length": 2,
        "stochrsi_slowd_length": 2,
        "stochrsi_upper": 70,
        "stochrsi_lower": 40,
        "stochrsi_adx_length": 30,
        "stochrsi_di_length": 12,
        "stochrsi_rsi_length": 14,
        "stochrsi_rsi_upper": 80,
        "stochrsi_rsi_lower": 25,
        "stochrsi_rsi_mom_thresh": 20,
        "stochrsi_mom_length": 20,
        "stochrsi_mom_ma_length": 10
    }

    strategy.set_params(params)

    start = dt[0]
    end = dt[1]

    data = await get_data_feed(mongo, _config, start, end)

    backtest = Backtest(strategy,
                        data_feed=data,
                        start=start,
                        end=end,
                        enable_plot=plot,
                        custom_config=_config)

    market = backtest.trader.markets[ex][0]
    sp = backtest.ohlcvs[ex][market]['1m'].iloc[0].open
    ep = backtest.ohlcvs[ex][market]['1m'].iloc[-1].close
    ch = ep / sp if ep >= sp else ((ep / sp) - 1)
    print(f"# {market}\n"
          f"# Starting price: {sp}\n"
          f"# Ending price:   {ep}\n"
          f"# Change(%):      {ch * 100}")

    report = backtest.run()

    print('-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=\n')
    print(market, ':', report['PL(%)'])
    print('\n-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=\n')

    print_to_file(backtest.margin_PLs, '../log/margin_pl.out')
    print_to_file(backtest.trader.wallet_history, '../log/wallet_history.out')
    print_to_file(backtest.trader.order_history[ex], '../log/order_history.out')

    # Print orders with PL < -30
    # for _, order in hist.items():
    #     # if order['PL'] < -30:
    #     if order['side'] == 'sell':
    #         pprint(order)

    return report


async def test_special_periods_of_markets(mongo, plot, log_signal):

    markets = [
        "BTC/USD",
        # "BCH/USD",
        # "ETH/USD",
        # "XRP/USD",

        # "EOS/USD",
        # "LTC/USD",
        # "NEO/USD",
        # "OMG/USD",

        # "ETC/USD",
        # "DASH/USD",
        # "IOTA/USD",
        # "XMR/USD",
        # "ZEC/USD"
    ]

    total_pl = 0

    for market in markets:
        report = await test_single_period(mongo, market, plot, log_signal)
        total_pl += report['PL(%)']

    print(f"Total PL(%): {total_pl/len(markets)}")


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument('--plot', action='store_true', help="Plot backtest results")
    parser.add_argument('--log-signal', action='store_true', help="Print strategy signal")

    argv = parser.parse_args()

    return argv


async def main():
    argv = parse_args()

    mongo = EXMongo(ssl=config['database']['ssl'])

    await test_special_periods_of_markets(mongo, argv.plot, argv.log_signal)


if __name__ == '__main__':
    run(main)
