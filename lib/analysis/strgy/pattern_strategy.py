from pprint import pprint

import logging

from analysis.indicators import Indicator
from analysis.strgy.base_strategy import SingleExchangeStrategy

logger = logging.getLogger()


class PatternStrategy(SingleExchangeStrategy):

    def __init__(self, ex, custom_config=None):
        super().__init__(ex, custom_config)
        self.ind = Indicator(custom_config=custom_config)

    def init_vars(self):
        self.margin = self._config['backtest']['margin']

    def fast_strategy(self):
        stop_loss = False
        stop_profit = False

        for market in self.markets:
            sig = self.calc_signal(market)
            self.execute_signal(sig, market, stop_loss, stop_profit)

    def execute_signal(self, sig, market, stop_loss=False, stop_profit=False):
        stop_loss = self.p['stop_loss_percent'] if stop_loss else None
        stop_profit = self.p['stop_profit_percent'] if stop_profit else None

        sig = sig.dropna()

        for dt, ss in sig.items():

            self.op_execute_position_stop(dt)
            self.op_force_liquidate_positions(dt)

            if ss > 0: # buy
                ss = abs(ss)
                self.op_clean_orders('sell', dt)
                curr = self.trader.quote_balance(market)
                cost = ss / 100 * self.trader.op_wallet[self.ex][curr] * self.p['trade_portion']
                self.op_buy(dt, market, cost, margin=self.margin, stop_loss=stop_loss, stop_profit=stop_profit)

            elif ss < 0: # sell
                ss = abs(ss)
                self.op_clean_orders('buy', dt)

                if self.margin:
                    curr = self.trader.quote_balance(market)
                else:
                    curr = self.trader.base_balance(market)

                cost = ss / 100 * self.trader.op_wallet[self.ex][curr] * self.p['trade_portion']
                self.op_sell(dt, market, cost, margin=self.margin, stop_loss=stop_loss, stop_profit=stop_profit)

            else:  # ss == 0
                # Close all positions and cancel all orders
                self.op_clean_orders('all', dt)

    def calc_signal(self, market):
        """ Main algorithm which calculates signals.
            Returns {signal, timeframe}
        """
        ohlcv = self.ohlcvs[market][self.trader.config['indicator_tf']]
        # sig = self.ind.wvf_sig(ohlcv)
        # sig = self.ind.rsi_sig(ohlcv)
        # sig = self.ind.ann_v3_sig(ohlcv)
        # sig = self.ind.vwma_sig(ohlcv)
        # sig = self.ind.vwma_ma_sig(ohlcv)
        # sig = self.ind.hma_sig(ohlcv)
        # sig = self.ind.hma_ma_sig(ohlcv)
        sig = self.ind.dmi_sig(ohlcv)
        # sig = self.ind.mom_sig(ohlcv)

        return sig
