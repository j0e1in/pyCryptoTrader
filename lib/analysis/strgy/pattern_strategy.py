from pprint import pprint
from datetime import timedelta

import logging
import matplotlib.pyplot as plt

from analysis.indicators import Indicator
from analysis.strgy.base_strategy import SingleExchangeStrategy

from ipdb import set_trace as trace

logger = logging.getLogger()


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
            self.stop_loss(market, dt)
            self.stop_profit(market, dt)

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
        ohlcv = self.ohlcvs[market][self.trader.config['indicator_tf']]
        # wvf = self.ind.wvf_sig(ohlcv)
        # rsi = self.ind.rsi_sig(ohlcv)
        # ann = self.ind.ann_v3_sig(ohlcv)
        # vwma = self.ind.vwma_sig(ohlcv)
        # vwma_ma = self.ind.vwma_ma_sig(ohlcv)
        # hma = self.ind.hma_sig(ohlcv)
        # hma_ma = self.ind.hma_ma_sig(ohlcv)
        dmi = self.ind.dmi_sig(ohlcv)

        return dmi

    def stop_loss(self, market, end):
        for id, pos in self.trader.op_positions[self.ex].items():
            if pos['market'] != market:
                continue

            start = pos['op_open_time'] + timedelta(minutes=1)
            ohlcv = self.trader.ohlcvs[self.ex][market][self.trader.config['indicator_tf']][start:end]
            if start == end:
                logger.warn('start == end')

            if len(ohlcv) > 0:
                target_low  = pos['op_open_price'] * (1 - self.p['stop_loss_percent'])
                target_high = pos['op_open_price'] * (1 + self.p['stop_loss_percent'])

                if pos['side'] == 'buy' \
                and ohlcv.low.min() < target_low:
                    dt = ohlcv[ohlcv.low < target_low].iloc[0].name
                    self.append_op(self.trader.op_close_position(pos, dt))

                    if self._config['mode'] == 'debug':
                        logger.debug(f"Stop loss @ {ohlcv.loc[dt].close} ({dt})")

                elif pos['side'] == 'sell' \
                and ohlcv.high.max() > target_high:
                    dt = ohlcv[ohlcv.high > target_high].iloc[0].name
                    self.append_op(self.trader.op_close_position(pos, dt))

                    if self._config['mode'] == 'debug':
                        logger.debug(f"Stop loss @ {ohlcv.loc[dt].close} ({dt})")

    def stop_profit(self, market, end):
        for id, pos in self.trader.op_positions[self.ex].items():
            pass





