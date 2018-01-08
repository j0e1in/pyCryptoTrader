from pprint import pprint
import talib.abstract as talib_abs # ndarray/dataframe as input
import talib # ndarray as input
import numpy as np
import pandas as pd
import math

from ipdb import set_trace as trace

from strgy.base_strategy import SingleExchangeStrategy
from utils import config
from indicators import Indicator


class PatternStrategy(SingleExchangeStrategy):

    def __init__(self, ex, custom_config=None):
        super().__init__(ex, custom_config)
        self.ind = Indicator(custom_config=custom_config)

    def init_vars(self):
        self.margin = self._config['backtest']['margin']

    def fast_strategy(self):

        for market in self.markets:

            sig = self.wvf(market)
            sig = sig.dropna()

            for dt, ss in sig.items():

                if ss > 0: # buy
                    ss = abs(ss)
                    self.op_clean_orders('sell', dt)
                    curr = self.trader.quote_balance(market)
                    cost = abs(ss) / 100 * self.trader.op_wallet[self.ex][curr] * self.p['trade_portion']
                    self.op_buy(dt, market, cost, margin=self.margin)

                elif ss < 0: # sell
                    ss = abs(ss)
                    self.op_clean_orders('buy', dt)

                    if self.margin:
                        curr = self.trader.quote_balance(market)
                    else:
                        curr = self.trader.base_balance(market)

                    cost = ss / 100 * self.trader.op_wallet[self.ex][curr] * self.p['trade_portion']
                    self.op_sell(dt, market, cost, margin=self.margin)

    def rsi(self, market):
        return self.ind.rsi(self.ohlcvs[market][self.p['rsi_tf']])

    def wvf(self, market):
        return self.ind.william_vix_fix_v3(self.ohlcvs[market][self.p['wvf_tf']])