from datetime import datetime

import copy
import logging
import numpy as np
import pprint

from trading.strgy.base_strategy import SingleEXStrategy
from trading.indicators import Indicator
from utils import \
    is_within, \
    near_end, \
    near_start, \
    tf_td, \
    utc_now

logger = logging.getLogger()


class PatternStrategy(SingleEXStrategy):

    def __init__(self, trader, custom_config=None):
        super().__init__(trader, custom_config)
        self.ind = Indicator(custom_config=self._config)
        self.last_sig_execution = {
            'conf': None,
            'time': None,
        }

    def init_vars(self):
        """ Variables declared here are reset everytime when ohlcv is updated. """
        self.margin = self.trader.config['margin']

    async def strategy(self):

        async def exec_sig(sig, market, use_prev_sig=False):
            conf = await self.execute_sig(sig, market, use_prev_sig=use_prev_sig)
            self.last_sig_execution['conf'] = conf
            self.last_sig_execution['time'] = utc_now()

        last_reset_time = datetime(1970, 1, 1)

        signals = {}
        for market in self.trader.ex.markets:
            signals[market] = self.calc_signal(market)

        market_ranks = self.rank_markets()
        for market in market_ranks:
            sig = signals[market]
            tf = self.trader.config['indicator_tf']
            td = tf_td(tf)

            # Ensure ohlcv is up-to-date
            if is_within(sig.index[-1], td):

                if not self.last_sig_execution['conf']:

                    # case 1: No sig has been executed in current interval
                    if near_end(sig.index[-1], td):
                        await exec_sig(sig, market)

                    # case 2: Sig is not executed on last period (activated at last second)
                    elif near_start(sig.index[-1], td):
                        await exec_sig(sig, market, use_prev_sig=True)

                # case 3: A sig of the period has already been executed but it changed
                else:
                    conf = None
                    use_prev_sig = False

                    # If last execution is more than 5 min (in 1h timeframe) ago, than execute
                    if near_end(sig.index[-1], td) \
                    and not is_within(self.last_sig_execution['time'], td / 12):
                        conf = sig[-1]
                        use_prev_sig = False

                    # If at a new interval but the last change has not been executed
                    elif near_start(sig.index[-1], td):
                        conf = sig[-2]
                        use_prev_sig = True

                    if conf and conf != self.last_sig_execution['conf']:
                        await exec_sig(sig, market, use_prev_sig=use_prev_sig)

            # Reset last_sig_execution on new period
            if near_start(sig.index[-1], td) \
            and not is_within(last_reset_time, tf_td(tf) / 2):
                self.last_sig_execution['conf'] = None
                self.last_sig_execution['time'] = None
                last_reset_time = utc_now()

        return signals

    async def execute_sig(self, sig, market, use_prev_sig=False):
        action = None
        succ = False
        conf = sig[-1] if not use_prev_sig else sig[-2]

        if conf > 0:
            logger.debug(pprint.pformat(sig[-10:]))
            action = 'long'
            succ = await self.trader.long(market, conf, type='limit')
        elif conf < 0:
            logger.debug(pprint.pformat(sig[-10:]))
            action = 'short'
            succ = await self.trader.short(market, conf, type='limit')

        return action if succ else None

    def calc_signal(self, market):
        """ Main algorithm which calculates signals.
            Returns {signal, timeframe}
        """
        self.ind.change_param_set(market)
        self.p = self.ind.p

        ohlcv = self.trader.ohlcvs[market][self.trader.config['indicator_tf']]
        sig = self.ind.stoch_rsi_sig(ohlcv)

        return sig

    def rank_markets(self):
        """ Rank markets' profitability.
            Returns a list of markets.
        """
        # TODO

        # Current method: hard coded market rank base on backtest profitibitlity
        backtest_profit_rank = [
            "XRP/USD",
            "BCH/USD",
            "BTC/USD",
            "ETH/USD",
        ]

        trade_markets = copy.deepcopy(self.trader.ex.markets)
        rank = []

        for market in backtest_profit_rank:
            if market in trade_markets:
                rank.append(market)

        trade_markets = [market for market in trade_markets if market not in rank]
        rank += trade_markets
        return rank
