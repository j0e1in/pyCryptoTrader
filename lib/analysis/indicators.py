from ipdb import set_trace as trace
from pprint import pprint
import talib.abstract as talib_abstract # ndarray/dataframe as input
import talib # ndarray as input
import pandas as pd
import numpy as np

from utils import config


BUY = 1
SELL = -1


class Indicator():

    def __init__(self, custom_config=None):
        _config = custom_config if custom_config else config
        self.p = _config['params']

    def rsi(self, ohlcv):
        ind = talib_abstract.RSI(ohlcv, timeperiod=self.p['rsi_period'])

        rise = self.is_rising(ind)
        drop = self.is_dropping(ind)

        exceed_lower_bound = ind < self.p['rsi_lower_bound']
        exceed_upper_bound = ind > self.p['rsi_upper_bound']

        buy_sig = rise & exceed_lower_bound
        sell_sig = drop & exceed_upper_bound

        buy_sig = pd.Series([BUY if i else np.nan for i in buy_sig], index=buy_sig.index)
        sell_sig = pd.Series([SELL if i else np.nan for i in sell_sig], index=sell_sig.index)
        sig = buy_sig.combine(sell_sig, lambda x, y: x if x == BUY else y)

        # Convert buy/sell signal to confidence -100(buy) ~ 100(sell)
        trend = 0
        repeat = 0
        tmp_sig = sig.dropna()
        conf = pd.Series(index=ohlcv.index)

        for dt, ss in tmp_sig.items():
            if ss != trend and trend != 0:
                trend = ''
                repeat = 0

            trend = ss
            repeat += 1
            conf[dt] = self.p['rsi_conf'] * repeat

            if ss == SELL:
                conf[dt] = conf[dt] * -1

        self.verify_confidence(conf)
        self.cap_confidence(conf)

        return conf

    def william_vix_fix_v3(self, ohlcv):
        # Inputs Tab Criteria.
        lbsdh = self.p['wvf_lbsdh']     # LookBack Period Standard Deviation High
        bbl = self.p['wvf_bbl']         # Bolinger Band Length
        bbsd = self.p['wvf_bbsd']       # Bollinger Band Standard Devaition Up (1.0-5.0)
        lbph = self.p['wvf_lbph']       # Look Back Period Percentile High
        ph = self.p['wvf_ph']           # Highest Percentile - 0.90=90%, 0.95=95%, 0.99=99%

        # Criteria for Down Trend Definition for Filtered Pivots and Aggressive Filtered Pivots
        ltLB = self.p['wvf_ltLB']       # Long-Term Look Back Current Bar Has To Close Below This Value OR Medium Term--Default=40 (25-99)
        mtLB = self.p['wvf_mtLB']       # Medium-Term Look Back Current Bar Has To Close Below This Value OR Long Term--Default=14 (10-20)
        strg = self.p['wvf_strg']         # Entry Price Action Strength--Close > X Bars Back---Default=3 (1-9)

        def highest(ss, n):
            """ Highest value for a given number of bars back. """
            tmp = pd.Series(index=ss.index)
            for i in np.arange(len(ss)):
                m = max(0, i+0-n)
                tmp[i] = ss[m:i+0].max()
            return tmp

        def stdev(ss, n):
            """ Standard deviation of max last n elements in a series. """
            tmp = pd.Series(index=ss.index)
            for i in np.arange(len(ss)):
                m = max(0, i+0-n)
                tmp[i] = np.std(ss[m:i+0])
            return tmp

        open = ohlcv.open
        high = ohlcv.high
        low = ohlcv.low
        close = ohlcv.close

        # Williams Vix Fix Formula
        wvf = (highest(close, lbsdh) - low) / highest(close, lbsdh) * 100
        sDev = bbsd * stdev(wvf, bbl)

        midLine = talib.SMA(np.asarray(wvf), bbl)
        midLine = pd.Series(midLine, index=wvf.index)
        lowerBand = midLine - sDev
        upperBand = midLine + sDev
        rangeHigh = (highest(wvf, lbph)) * ph

        wvf_s = wvf.shift(1)
        upperBand_s = upperBand.shift(1)
        rangeHigh_s = rangeHigh.shift(1)

        # Signals
        wvf_sig = (wvf >= upperBand) | (wvf >= rangeHigh)  # True: dropping(lime color), False: rising

        # When wvf turns from True to False (original version, first N signals are False)
        # rise_sig = ( (wvf_s >= upperBand_s) | (wvf_s >= rangeHigh_s) ) \
        #          & ( (wvf < upperBand) & (wvf < rangeHigh) )

        rise_sig = (wvf_sig.shift(1) | wvf_sig) & wvf_sig.shift(1) & ~wvf_sig
        drop_sig = (wvf_sig.shift(1) | wvf_sig) & (~wvf_sig).shift(1) & wvf_sig

        conf = pd.Series(index=ohlcv.index)
        conf[rise_sig.index[rise_sig == True]] = BUY * self.p['wvf_conf']
        conf[drop_sig.index[drop_sig == True]] = SELL * self.p['wvf_conf']

        # --------------------------------------------------------------- #

        # Filtered Bar Criteria
        upRange = (low > low.shift(1)) & (close > high.shift(1))
        upRange_Aggr = (close > close.shift(1)) & (close > open.shift(1))

        # Filtered Criteria
        filtered = ( (wvf_s >= upperBand_s) | (wvf_s >= rangeHigh_s) ) \
                 & ( (wvf < upperBand) & (wvf < rangeHigh) )

        filtered_aggr = ( (wvf_s >= upperBand_s) | (wvf_s >= rangeHigh_s) ) \
                 & (~((wvf < upperBand) & (wvf < rangeHigh)))

        # Filtered entry
        filtered_entry = upRange & (close > close[strg]) & ((close < close[ltLB]) | (close < close[mtLB])) & filtered

        # Aggressive filtered entry
        filtered_entry_aggr = upRange_Aggr & (close > close[strg]) & ((close < close[ltLB]) | (close < close[mtLB])) & filtered_aggr

        self.verify_confidence(conf)
        self.cap_confidence(conf)

        return conf

    def calc_abs_talib_func(self, ta_func, market=None, tf=None, **ta_args):
        """ Run abstract talib function. """
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

    @staticmethod
    def filter_repeat_buy_sell(sig):
        """ Filter repeated buy/sell signal.
            eg. BBSBBSSB => BSBSB
        """
        buy_sell = 'buy'
        filtered_sig = pd.Series(index=sig.index)

        for idx in sig.index:
            if sig[idx] == BUY and buy_sell == 'buy':
                filtered_sig[idx] = BUY
                buy_sell = 'sell'

            elif sig[idx] == SELL and buy_sell == 'sell':
                filtered_sig[idx] = SELL
                buy_sell = 'buy'

        return filtered_sig

    @staticmethod
    def is_dropping(x, threshold=0):
        """ True if current value is less than previous by `threshold` amount. """
        r = x < (x.shift(1) - threshold)
        return r

    @staticmethod
    def is_rising(x, threshold=0):
        """ True if current value is greater than previous by `threshold` amount. """
        r = x > (x.shift(1) + threshold)
        return r

    @staticmethod
    def cap_confidence(conf):
        conf[conf > 100] = 100
        conf[conf < -100] = -100
        return conf

    @staticmethod
    def verify_confidence(conf):
        """ Check if confidence contains BUY or SELL value (which is invalid). """
        if ((conf == BUY) | (conf == SELL)).any():
            raise ValueError("Confidence is invalid.")
