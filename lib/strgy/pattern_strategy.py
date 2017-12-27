from pprint import pprint
import talib.abstract as talib
import numpy as np
import pandas as pd

from strgy.base_strategy import SingleExchangeStrategy
from utils import visualize_dict


class PatternStrategy(SingleExchangeStrategy):

    def __init__(self, ex):
        super().__init__(ex)

    def init_vars(self):
        self.params = {
            'rsi_tf': '30m',
            'rsi_period': 5,
            'rsi_upper_bound': 70,
            'rsi_lower_bound': 30,
        }
        self.p = self.params
        self.trade_portion = 0.9
        self.margin = False

    def fast_strategy(self):
        indicators = {}

        indicators['rsi'] = self.calc_talib_func(talib.RSI, period=self.p['rsi_period'])

        for market in self.markets:
            ind = indicators['rsi'][market][self.p['rsi_tf']]

            peak_low = is_peak_low(ind)
            peak_high = is_peak_high(ind)

            exceed_lower_bound = ind > self.p['rsi_lower_bound']
            exceed_upper_bound = ind > self.p['rsi_upper_bound']

            buy_sig = peak_low & exceed_lower_bound
            sell_sig = peak_high & exceed_upper_bound

            buy_sig = pd.Series(['B' if i else np.nan for i in buy_sig], index=buy_sig.index)
            sell_sig = pd.Series(['S' if i else np.nan for i in sell_sig], index=sell_sig.index)

            sig = buy_sig.combine(sell_sig, lambda x, y: x if x == 'B' else y).dropna()

            buy_sell = 'buy'
            filtered_sig = pd.Series(index=sig.index)

            for idx in sig.index:
                if sig[idx] == 'B' and buy_sell == 'buy':
                    filtered_sig[idx] = 'B'
                    buy_sell = 'sell'

                elif sig[idx] == 'S' and buy_sell == 'sell':
                    filtered_sig[idx] = 'S'
                    buy_sell = 'buy'

            filtered_sig = filtered_sig.dropna()

            for dt, sig in filtered_sig.items():
                if sig == 'B':
                    curr = self.trader.quote_balance(market)
                    cost = self.trader.op_wallet[self.ex][curr] * self.trade_portion
                    self.op_buy(dt, market, cost, margin=self.margin)

                elif sig == 'S':
                    curr = self.trader.base_balance(market)
                    cost = self.trader.op_wallet[self.ex][curr]
                    self.op_sell(dt, market, cost, margin=self.margin)

    def calc_talib_func(self, ta_func, market=None, tf=None, **ta_args):
        if market:
            if tf:
                return ta_func(self.ohlcvs[market][tf], **ta_args)
            else:
                results = {}
                for tf, ohlcv in self.ohlcvs[market].items():
                    results[tf] = ta_func(ohlcv, **ta_args)
        else:
            results = {}
            for market, tfs in self.ohlcvs.items():
                results[market] = {}
                for tf, ohlcv in tfs.items():
                    results[market][tf] = ta_func(ohlcv, **ta_args)

        return results

    def merge_to_ohlcv(self, dfs, ohlcvs):
        """ Merge dfs to ohlcvs as new column(s).
            Param
                dfs: Same format as ohlcvs, either `a dataframe` or `dict[market][tf]`.
                     Must have same indeies as ohlcv.
                ohlcvs: Sames format as dfs
        """
        merged = {}

        if isinstance(dfs, pd.DataFrame) and isinstance(ohlcvs, pd.DataFrame):
            merged = pd.concat([dfs, ohlcvs], axis=1)

        elif isinstance(dfs, dict) and isinstance(ohlcvs, dict)\
                and self.check_dict_hierarchy(dfs, 2)\
                and self.check_dict_hierarchy(ohlcvs, 2):
            for market, tfs in dfs.items():
                merged[market] = {}
                for tf, ohlcv in tfs.items():
                    merged[market][tf] = pd.concat([dfs[market][tf], ohlcvs[market][tf]], axis=1)
        else:
            raise ValueError("dfs and ohlcvs are not of the same format, merge can't be performed.")

        return merged

    @staticmethod
    def check_dict_hierarchy(d, hierarchy):

        def _check(d, hierarchy):
            if hierarchy <= 0:
                return True if not isinstance(d, dict) else False

            if not isinstance(d, dict):
                return False

            result = True
            for k in d.keys():
                if not _check(d[k], hierarchy-1):
                    result = False

            return result

        return _check(d, hierarchy)


def is_peak_high(x):
    x1 = x > x.shift(1)  # prev
    x2 = x > x.shift(-1)  # next
    return x1 & x2


def is_peak_low(x):
    x1 = x < x.shift(1)  # prev
    x2 = x < x.shift(-1)  # next
    return x1 & x2
