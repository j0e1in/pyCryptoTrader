from pprint import pprint
from datetime import timedelta

import logging
import matplotlib.pyplot as plt

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
        # sig = self.ind.wvf_sig(ohlcv)
        # sig = self.ind.rsi_sig(ohlcv)
        # sig = self.ind.ann_v3_sig(ohlcv)
        # sig = self.ind.vwma_sig(ohlcv)
        # sig = self.ind.vwma_ma_sig(ohlcv)
        # sig = self.ind.hma_sig(ohlcv)
        # sig = self.ind.hma_ma_sig(ohlcv)
        sig = self.ind.dmi_sig(ohlcv)

        return sig

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
                        logger.debug(f"Stop buy loss @ {ohlcv.loc[dt].close} ({dt})")

                elif pos['side'] == 'sell' \
                and ohlcv.high.max() > target_high:
                    dt = ohlcv[ohlcv.high > target_high].iloc[0].name
                    self.append_op(self.trader.op_close_position(pos, dt))

                    if self._config['mode'] == 'debug':
                        logger.debug(f"Stop sell loss @ {ohlcv.loc[dt].close} ({dt})")

    def stop_profit(self, market, end):
        for id, pos in self.trader.op_positions[self.ex].items():
            if pos['market'] != market:
                continue

            start = pos['op_open_time'] + timedelta(minutes=1)
            ohlcv = self.trader.ohlcvs[self.ex][market][self.trader.config['indicator_tf']][start:end]
            if start == end:
                logger.warn('start == end')

            if len(ohlcv) > 0:
                if pos['side'] == 'buy':
                    for dt, oh in ohlcv.iterrows():
                        cur_high = ohlcv[:dt + timedelta(minutes=1)].close.max()
                        target_low = cur_high * (1 - self.p['stop_profit_percent'])

                        if target_low > pos['op_open_price'] and oh.close < target_low:
                            self.append_op(self.trader.op_close_position(pos, dt))

                            if self._config['mode'] == 'debug':
                                logger.debug(f"Stop buy profit @ {ohlcv.loc[dt].close} ({dt})")

                            break

                elif pos['side'] == 'sell':
                    for dt, oh in ohlcv.iterrows():
                        cur_low = ohlcv[:dt + timedelta(minutes=1)].close.min()
                        target_high = cur_low * (1 + self.p['stop_profit_percent'])

                        if target_high < pos['op_open_price'] and oh.close > target_high:
                            self.append_op(self.trader.op_close_position(pos, dt))

                            if self._config['mode'] == 'debug':
                                logger.debug(f"Stop sell profit @ {ohlcv.loc[dt].close} ({dt})")

                            break







