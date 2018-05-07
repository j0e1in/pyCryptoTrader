from pprint import pprint

import logging
import numpy as np

from analysis.strategy import SingleExchangeStrategy

logger = logging.getLogger('pyct')


class PatternStrategy(SingleExchangeStrategy):

    def __init__(self, ex, custom_config=None):
        super().__init__(ex, custom_config)

    def init_vars(self):
        self.margin = self._config['backtest']['margin']

    def fast_strategy(self):
        stop_loss = False
        stop_profit = False

        for market in self.markets:
            if market in self.params:
                param = self.params[market]
            else:
                param = self.params['common']

            sig = self.calc_signal(market, param)
            self.execute_signal(sig, market, stop_loss, stop_profit)

            if self._config['analysis']['log_signal']:
                print(market, 'signal:')
                print(sig)

    def calc_signal(self, market, param):
        """ Main algorithm which calculates signals.
            Returns {signal, timeframe}
        """
        self.ind.p = param

        ohlcv = self.ohlcvs[market][self.trader.config['indicator_tf']]
        sig = self.ind.stoch_rsi_sig(ohlcv)

        buff_len = self._config['analysis']['ohlcv_buffer_bars']
        if buff_len >= len(sig):
            raise RuntimeError("ohlcv_buffer_bars > signal length")

        sig[:buff_len] = np.nan
        return sig

    def execute_signal(self, sig, market, stop_loss=False, stop_profit=False):
        stop_loss = self.ind.p['stop_loss_percent'] if stop_loss else None
        stop_profit = self.ind.p['stop_profit_percent'] if stop_profit else None

        sig = sig.dropna()

        for dt, ss in sig.items():

            self.op_execute_position_stop(dt)
            # self.op_force_liquidate_positions(dt)

            if ss > 0: # buy
                ss = abs(ss)
                self.op_clean_orders('sell', dt)
                curr = self.trader.quote_balance(market)
                cost = ss / 100 * self.trader.op_wallet[self.ex][curr] * self.ind.p['trade_portion']
                self.op_buy(dt, market, cost, margin=self.margin, stop_loss=stop_loss, stop_profit=stop_profit)

            elif ss < 0: # sell
                ss = abs(ss)
                self.op_clean_orders('buy', dt)

                if self.margin:
                    curr = self.trader.quote_balance(market)
                else:
                    curr = self.trader.base_balance(market)

                cost = ss / 100 * self.trader.op_wallet[self.ex][curr] * self.ind.p['trade_portion']
                self.op_sell(dt, market, cost, margin=self.margin, stop_loss=stop_loss, stop_profit=stop_profit)

            else:  # ss == 0
                # Close all positions and cancel all orders
                self.op_clean_orders('all', dt)
