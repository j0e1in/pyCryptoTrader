from pprint import pprint

import matplotlib.pyplot as plt

from analysis.indicators import Indicator
from analysis.strgy.base_strategy import SingleExchangeStrategy

from ipdb import set_trace as trace

class PatternStrategy(SingleExchangeStrategy):

    def __init__(self, ex, custom_config=None):
        super().__init__(ex, custom_config)
        self.ind = Indicator(custom_config=custom_config)

    def init_vars(self):
        self.margin = self._config['backtest']['margin']

    def fast_strategy(self):
        for market in self.markets:
            sig = self.calc_signal(market)
            self.execute_signal(sig, market)

    def execute_signal(self, sig, market):
        sig = sig.dropna()
        for dt, ss in sig.items():
            if ss > 0: # buy
                ss = abs(ss)
                self.op_clean_orders('sell', dt)
                curr = self.trader.quote_balance(market)
                cost = ss / 100 * self.trader.op_wallet[self.ex][curr] * self.p['trade_portion']
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

            else:  # ss == 0
                # Close all positions and cancel all orders
                self.op_clean_orders('all', dt)

    def calc_signal(self, market):
        """ Main algorithm which calculates signals.
            Returns {signal, timeframe}
        """
        wvf = self.ind.wvf_sig(self.ohlcvs[market][self.p['wvf_tf']])
        # rsi = self.ind.rsi_sig(self.ohlcvs[market][self.p['rsi_tf']])
        # ann = self.ind.ann_v3_sig(self.ohlcvs[market][self.p['ann_tf']])
        # vwma = self.ind.vwma_sig(self.ohlcvs[market][self.p['vwma_tf']])
        # vwma_ma = self.ind.vwma_ma_sig(self.ohlcvs[market][self.p['vwma_tf']])
        # hma = self.ind.hma_sig(self.ohlcvs[market][self.p['hma_tf']])
        # hma_ma = self.ind.hma_ma_sig(self.ohlcvs[market][self.p['hma_tf']])
        dmi = self.ind.dmi_sig(self.ohlcvs[market][self.p['dmi_tf']])

        return dmi
