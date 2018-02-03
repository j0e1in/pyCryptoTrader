from utils import config, is_within, near_end

import logging
import numpy as np

from trading.strgy.base_strategy import SingleEXStrategy
from trading.indicators import Indicator
from utils import timeframe_timedelta

from ipdb import set_trace as trace
import pprint

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

        async def exec_sig(sig, prev=False):
            conf = await self.execute_sig(sig, prev=prev)
            self.last_sig_execution['conf'] = conf
            self.last_sig_execution['time'] = utc_now()

        signals = {}
        for market in self.trader.markets:
            signals[market] = self.calc_signal(market)

        markets_order = self.rank_market(signals)
        for market in markets_order:
            sig = signals[market]['sig']
            tf = signals[market]['tf']

            trace()

            td = timeframe_timedelta(tf)

            # Ensure ohlcv is up-to-date
            if is_within(sig.index[-1], td):

                if not self.last_sig_execution['conf']:

                    # case 1: No sig has been executed
                    if near_end(sig.index[-1], td):
                        await exec_sig(sig)

                    # case 2: Sig is not executed on last period (activated at last second)
                    elif near_start(sig.index[-1], td):
                        await exec_sig(sig, prev=True)

                # case 3: A sig of the period has already been executed but it changed
                else:
                    conf = None
                    prev = False

                    # If last execution is more than 5 min (in 1h timeframe) ago, than execute
                    if near_end(sig.index[-1], td) \
                    and not is_within(self.last_sig_execution['time'], td / 12):
                        conf = sig[-1]
                        prev = False

                    elif near_start(sig.index[-1], td):
                        conf = sig[-2]
                        prev = True

                    if conf and conf != self.last_sig_execution['conf']:
                        await exec_sig(sig)

                    # Or starting a new period but the last change has not been executed
                        await exec_sig(sig, prev=True)

            # Reset last_sig_execution on new period
            if near_start(sig.index[-1], td):
                self.last_sig_execution['conf'] = None
                self.last_sig_execution['time'] = None

    async def execute_sig(self, sig, prev=False):
        action = None
        succ = False
        conf = sig[-1] if not prev else sig[-2]

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
        # sig = self.wvf(market)
        # tf = self.p['wvf_tf']

        sig = self.hma(market)
        tf = self.p['hma_tf']

        return {
            'sig': sig,
            'tf': tf
        }

    def rsi(self, market):
        return self.ind.rsi(self.trader.ohlcvs[market][self.p['rsi_tf']])

    def wvf(self, market):
        return self.ind.william_vix_fix_v3(self.trader.ohlcvs[market][self.p['wvf_tf']])

    def hma(self, market):
        return self.ind.hull_moving_average(self.trader.ohlcvs[market][self.p['hma_tf']])

    def rank_market(self, signals):
        """ Rank markets' profitability.
            Returns a list of markets.
        """
        # TODO: (HIGH PRIOR)

        # Idea 1: calculate smoothness in past 1-4 days
        #         lower the smoothness higher the rank

        # Current method: no ranking, by the order of self.trader.markets
        return self.trader.markets

