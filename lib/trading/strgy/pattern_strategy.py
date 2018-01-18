from utils import config, is_within, near_end

from trading.strgy.base_strategy import SingleEXStrategy
from trading.indicators import Indicator

from ipdb import set_trace as trace
from pprint import pprint


class PatternStrategy(SingleEXStrategy):

    def __init__(self, trader, custom_config=None):
        super().__init__(trader, custom_config)
        self.ind = Indicator(custom_config=self._config)

    def init_vars(self):
        self.margin = self.trader.config['margin']

    def strategy(self):

        signals = {}
        for market in self.trader.markets:
            signals[market] = self.calc_signal(market)

        markets_order = self.rank_market(signals)
        for market in markets_order:
            sig = signals[market]['sig']
            tf = signals[market]['tf']

            # if near start use previous sig? -> don't apply to '1m'
            if is_within(sig.index[-1], tf) \
            and near_end(sig.index[-1], tf):
                conf = sig[-1]


                if conf > 0:
                    pprint(sig[-10:])
                    self.trader.long(market, conf, type='limit')
                elif conf < 0:
                    pprint(sig[-10:])
                    self.trader.short(market, conf, type='limit')
                else:
                    continue


    def calc_signal(self, market):
        """ Main algorithm where calculates signals.
            Returns (signal, timeframe)
        """
        return {
            'sig': self.wvf(market),
            'tf': self.p['wvf_tf'],
        }

    def rsi(self, market):
        return self.ind.rsi(self.trader.ohlcvs[market][self.p['rsi_tf']])

    def wvf(self, market):
        return self.ind.william_vix_fix_v3(self.trader.ohlcvs[market][self.p['wvf_tf']])

    def rank_market(self, signals):
        """ Rank markets' profitability.
            Returns a list of markets.
        """
        # TODO: (HIGH PRIOR)

        # Idea 1: calculate smoothness in past 1-4 days
        #         lower the smoothness higher the rank

        # Current method: no ranking, by the order of self.trader.markets
        return self.trader.markets
