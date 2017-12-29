from pprint import pprint
import talib.abstract as talib_abs # ndarray/dataframe as input
import talib # ndarray as input
import numpy as np
import pandas as pd
import math

from ipdb import set_trace as trace

from strgy.base_strategy import SingleExchangeStrategy
from utils import config

BUY = 1
SELL = -1


class PatternStrategy(SingleExchangeStrategy):

    def __init__(self, ex):
        super().__init__(ex)

    def init_vars(self):
        self.params = {
            'rsi_tf': '1h',
            'rsi_period': 14,
            'rsi_upper_bound': 70,
            'rsi_lower_bound': 30,
            'rsi_conf': 40,
            'wvf_tf': '1h',
            'wvf_conf': 50,
        }
        self.p = self.params
        self.trade_portion = 0.5
        self.margin = True

    def fast_strategy(self):
        indicators = {}

        indicators['rsi'] = self.calc_abs_talib_func(talib_abs.RSI, timeperiod=self.p['rsi_period'])
        wvf_sig = self.william_vix_fix_v3(self.ohlcvs[self.markets[0]][self.p['wvf_tf']])

        for market in self.markets:
            # sig = self.rsi_signal(indicators['rsi'][market][self.p['rsi_tf']])
            sig = wvf_sig
            sig = sig.dropna()

            if not config['matplot']['enable']:
                indicators['rsi'][market][self.p['rsi_tf']].plot()

            for dt, ss in sig.items():

                if ss > 0: # buy
                    ss = abs(ss)
                    self.op_clean_orders('sell', dt)
                    curr = self.trader.quote_balance(market)
                    cost = abs(ss) / 100 * self.trader.op_wallet[self.ex][curr] * self.trade_portion
                    self.op_buy(dt, market, cost, margin=self.margin)

                elif ss < 0: # sell
                    ss = abs(ss)
                    self.op_clean_orders('buy', dt)

                    if self.margin:
                        curr = self.trader.quote_balance(market)
                    else:
                        curr = self.trader.base_balance(market)

                    cost = ss / 100 * self.trader.op_wallet[self.ex][curr] * self.trade_portion
                    self.op_sell(dt, market, cost, margin=self.margin)

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

    def rsi_signal(self, ind):
        rise = is_rising(ind)
        drop = is_dropping(ind)

        exceed_lower_bound = ind < self.p['rsi_lower_bound']
        exceed_upper_bound = ind > self.p['rsi_upper_bound']

        buy_sig = rise & exceed_lower_bound
        sell_sig = drop & exceed_upper_bound

        # BUY == 'buy' SELL == 'sell'
        buy_sig = pd.Series([BUY if i else np.nan for i in buy_sig], index=buy_sig.index)
        sell_sig = pd.Series([SELL if i else np.nan for i in sell_sig], index=sell_sig.index)

        sig = buy_sig.combine(sell_sig, lambda x, y: x if x == BUY else y)

        # Convert buy/sell signal to confidence -100(buy) ~ 100(sell)
        conf = self.p['rsi_conf'] # absolute value
        trend = 0
        repeat = 0
        tmp_sig = sig.dropna()

        for dt, ss in tmp_sig.items():
            if ss != trend and trend != 0:
                trend = ''
                repeat = 0

            trend = ss
            repeat += 1
            sig[dt] = conf * repeat

            if ss == SELL:
                sig[dt] = sig[dt] * -1

        self.verify_confidence(sig)
        self.cap_confidence(sig)

        return sig

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
    def cap_confidence(conf):
        conf[conf > 100] = 100
        conf[conf < -100] = -100
        return conf

    @staticmethod
    def verify_confidence(conf):
        """ Check if confidence contains BUY or SELL value (which is invalid). """
        if ((conf == BUY) | (conf == SELL)).any():
            raise ValueError("Confidence is invalid.")

    def william_vix_fix_v3(self, ohlcv):
        # Inputs Tab Criteria.
        lbsdh = 22      # LookBack Period Standard Deviation High
        bbl = 20        # Bolinger Band Length
        bbsd = 2.0      # Bollinger Band Standard Devaition Up (1.0-5.0)
        lbph = 50       # Look Back Period Percentile High
        ph = .85        # Highest Percentile - 0.90=90%, 0.95=95%, 0.99=99%

        # Criteria for Down Trend Definition for Filtered Pivots and Aggressive Filtered Pivots
        ltLB = 40       # Long-Term Look Back Current Bar Has To Close Below This Value OR Medium Term--Default=40 (25-99)
        mtLB = 14       # Medium-Term Look Back Current Bar Has To Close Below This Value OR Long Term--Default=14 (10-20)
        str = 3         # Entry Price Action Strength--Close > X Bars Back---Default=3 (1-9)


        def highest(ss, n):
            """ Highest value for a given number of bars back. """
            tmp = pd.Series(index=ss.index)
            for i in np.arange(len(ss)):
                m = max(0, i+1-n)
                tmp[i] = ss[m:i+1].max()
            return tmp

        def stdev(ss, n):
            """ Standard deviation of max last n elements in a series. """
            tmp = pd.Series(index=ss.index)
            for i in np.arange(len(ss)):
                m = max(0, i+1-n)
                tmp[i] = np.std(ss[m:i+1])
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

        # Filtered Bar Criteria
        upRange = (low > low.shift(1)) & (close > high.shift(1))
        upRange_Aggr = (close > close.shift(1)) & (close > open.shift(1))

        wvf_s = wvf.shift(1)
        upperBand_s = upperBand.shift(1)
        rangeHigh_s = rangeHigh.shift(1)

        # Filtered Criteria
        filtered = ( (wvf_s >= upperBand_s) | (wvf_s >= rangeHigh_s) ) \
                 & ( (wvf < upperBand) & (wvf < rangeHigh) )

        filtered_aggr = ( (wvf_s >= upperBand_s) | (wvf_s >= rangeHigh_s) ) \
                    & ( ~( (wvf < upperBand) & (wvf < rangeHigh) ) )


        ## Signals
        wvf_sig = (wvf >= upperBand) | (wvf >= rangeHigh) # True: dropping, False: rising

        # When wvf turns from True to False
        rise_sig = ( (wvf_s >= upperBand_s) | (wvf_s >= rangeHigh_s) ) \
                   & ( (wvf < upperBand) & (wvf < rangeHigh) )

        rise_sig2 = (wvf_sig.shift(1) | wvf_sig) & wvf_sig.shift(1) & ~wvf_sig
        drop_sig2 = (wvf_sig.shift(1) | wvf_sig) & (~wvf_sig).shift(1) & wvf_sig

        # Filtered entry
        filtered_entry = upRange & (close > close[str]) & ( (close < close[ltLB]) | (close < close[mtLB]) ) & filtered

        # Aggressive filtered entry
        filtered_entry_aggr = upRange_Aggr & (close > close[str]) & ( (close < close[ltLB]) | (close < close[mtLB]) ) & filtered_aggr

        conf = pd.Series(index=ohlcv.index)
        conf[ rise_sig2.index[rise_sig2 == True] ] = BUY * self.p['wvf_conf']
        conf[ drop_sig2.index[drop_sig2 == True] ] = SELL * self.p['wvf_conf']

        return conf

        # wvf_sig.astype(int).plot()
        # rise_sig2.astype(int).plot()
        # drop_sig2.astype(int).plot()

        ## Plots for Williams Vix Fix Histogram and Alerts
        # plot(swvf and wvf ? wvf * -1 : na, title="Williams Vix Fix", style=columns, linewidth = 4, color=col)
        # plot(sa1 and alert1 ? alert1 : 0, title="Alert If WVF = True", style=line, linewidth=2, color=lime)
        # plot(sa2 and alert2 ? alert2 : 0, title="Alert If WVF Was True Now False", style=line, linewidth=2, color=aqua)
        # plot(sa3 and alert3 ? alert3 : 0, title="Alert Filtered Entry", style=line, linewidth=2, color=fuchsia)
        # plot(sa4 and alert4 ? alert4 : 0, title="Alert Aggressive Filtered Entry", style=line, linewidth=2, color=orange)


def is_dropping(x):
    x1 = x < x.shift(1)  # prev
    return x1


def is_rising(x):
    x1 = x > x.shift(1)  # prev
    return x1
