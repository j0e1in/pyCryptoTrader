from datetime import timedelta

try:
    import matplotlib.pyplot as plt
except ImportError:
    pass

import talib.abstract as talib_abstract # ndarray/dataframe as input
import talib # ndarray as input
import pandas as pd
import numpy as np
import math

from utils import config

from pprint import pprint

BUY = 1
SELL = -1


class Indicator():

    def __init__(self, custom_config=None):
        _config = custom_config if custom_config else config
        self.p = _config['analysis']['params']

    def rsi_sig(self, ohlcv):
        rsi = self.talib_s(talib.RSI, ohlcv.close, self.p['rsi_period'])

        adx, pdi, mdi = self.dmi(ohlcv, self.p['rsi_adx_length'], self.p['rsi_di_length'])

        upper = pd.Series(np.nan, index=ohlcv.index)
        lower = pd.Series(np.nan, index=ohlcv.index)
        conf  = pd.Series(np.nan, index=ohlcv.index)

        uptrend = pdi > mdi
        upper[uptrend == True] = self.p['rsi_uptrend_upper']
        upper[uptrend == False] = self.p['rsi_downtrend_upper']
        lower[uptrend == True] = self.p['rsi_uptrend_lower']
        lower[uptrend == False] = self.p['rsi_downtrend_lower']

        price_diff = ohlcv.close - ohlcv.open
        price_diff_prct = price_diff / ohlcv.close

        buy  = rsi < lower
        sell = rsi > upper

        # conf[(buy  == True) & (adx > self.p['rsi_adx_threshold'])] = self.p['rsi_conf']
        # conf[(sell == True) & (adx > self.p['rsi_adx_threshold'])] = -self.p['rsi_conf']

        # buy  = (buy  == True) & (price_diff < 0) & (adx > self.p['rsi_adx_threshold'])
        # sell = (sell == True) & (price_diff > 0) & (adx > self.p['rsi_adx_threshold'])
        # conf[buy]  = self.p['rsi_conf']
        # conf[sell] = -self.p['rsi_conf']

        buy  = (buy  == True) & (price_diff < 0) & (adx > self.p['rsi_adx_threshold']) & (price_diff_prct < 0.17)
        sell = (sell == True) & (price_diff > 0) & (adx > self.p['rsi_adx_threshold']) & (price_diff_prct < 0.17)
        conf[buy]  = self.p['rsi_conf']
        conf[sell] = -self.p['rsi_conf']

        last_conf = 0
        last_diff = 0
        for i in range(len(conf)):
            diff = ohlcv.iloc[i].close - ohlcv.iloc[i].open

            # # Liquidate position on first opposite trend bar
            # if (last_conf > 0 and last_diff > 0 and diff < 0) \
            # or (last_conf < 0 and last_diff < 0 and diff > 0):
            #     conf.iloc[i] = 0 # close positions
            #     last_conf = 0

            if (last_conf > 0 and last_diff < 0 and diff > 0) \
            or (last_conf < 0 and last_diff > 0 and diff < 0):
                conf.iloc[i] = 0 # close positions
                last_conf = 0

            elif not np.isnan(conf.iloc[i]):
                last_conf = conf.iloc[i]

            last_diff = diff

        self.verify_confidence(conf)
        self.cap_confidence(conf)

        return conf

    def wvf(self, ohlcv):
        """ William Vix Fix v3 """
        lbsdh = self.p['wvf_lbsdh']     # LookBack Period Standard Deviation High

        low = ohlcv.low
        close = ohlcv.close

        # Williams Vix Fix Formula
        wvf = (highest(close, lbsdh) - low) / highest(close, lbsdh) * 100
        return wvf

    def wvf_sig(self, ohlcv):
        # Inputs Tab Criteria.
        lbsdh = self.p['wvf_lbsdh']     # LookBack Period Standard Deviation High
        bbl = self.p['wvf_bbl']         # Bolinger Band Length
        bbsd = self.p['wvf_bbsd']       # Bollinger Band Standard Devaition Up (1.0-5.0)
        lbph = self.p['wvf_lbph']       # Look Back Period Percentile High
        ph = self.p['wvf_ph']           # Highest Percentile - 0.90=90%, 0.95=95%, 0.99=99%

        # Criteria for Down Trend Definition for Filtered Pivots and Aggressive Filtered Pivots
        ltLB = self.p['wvf_ltLB']       # Long-Term Look Back Current Bar Has To Close Below This Value OR Medium Term--Default=40 (25-99)
        mtLB = self.p['wvf_mtLB']       # Medium-Term Look Back Current Bar Has To Close Below This Value OR Long Term--Default=14 (10-20)
        strg = self.p['wvf_strg']       # Entry Price Action Strength--Close > X Bars Back---Default=3 (1-9)

        open = ohlcv.open
        high = ohlcv.high
        low = ohlcv.low
        close = ohlcv.close

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

    def hma(self, ss, ma='wma', length=None):
        """ Hull Moving Average """
        # Formula: HMA[i] = MA( (2*MA(input, length/2) - MA(input, length)), SQRT(length))
        if not length:
            length = self.p['hma_length']

        MA = getattr(talib, ma.upper())
        hma = MA((2 * MA(np.asarray(ss), length/2))
                    - MA(np.asarray(ss), length),
                math.sqrt(length))
        hma = pd.Series(hma, index=ss.index)
        return hma

    def hma_sig(self, ohlcv, ma='wma'):
        fk_period = self.p['hma_fk_period']
        fd_period = self.p['hma_fd_period']

        # Calculate indicators
        hma = self.hma(ohlcv.close, ma)
        adx, pdi, mdi = self.dmi(ohlcv, self.p['hma_adx_length'], self.p['hma_di_length'])
        # fastk, fastd = self.talib_s(talib.STOCHRSI, ohlcv.close, fastk_period=fk_period, fastd_period=fd_period)

        buy  = (hma.shift(2) >= hma.shift(1)) & (hma.shift(1) < hma) & (adx > self.p['hma_adx_thresh'])
        sell = (hma.shift(2) <= hma.shift(1)) & (hma.shift(1) > hma) & (adx > self.p['hma_adx_thresh'])

        # rsi_buy = fastk

        conf = pd.Series(index=ohlcv.index)
        conf[buy  == True] = BUY * self.p['hma_conf']
        conf[sell == True] = SELL * self.p['hma_conf']

        self.verify_confidence(conf)
        self.cap_confidence(conf)

        return conf

    def hma_ma_sig(self, ohlcv, ma='ema'):
        hma = self.hma(ohlcv.close, ma)
        MA = getattr(talib, ma.upper())
        hma_ma = self.talib_s(MA, hma, self.p['hma_ma_length'])
        rise_sig = (hma_ma.shift(2) >= hma_ma.shift(1)) & (hma_ma.shift(1) < hma_ma)
        drop_sig = (hma_ma.shift(2) <= hma_ma.shift(1)) & (hma_ma.shift(1) > hma_ma)

        conf = pd.Series(index=ohlcv.index)
        conf[rise_sig.index[rise_sig == True]] = BUY * self.p['hma_conf']
        conf[drop_sig.index[drop_sig == True]] = SELL * self.p['hma_conf']

        self.verify_confidence(conf)
        self.cap_confidence(conf)

        return conf

    def vwma(self, ss, vol, length=None):
        """ Volume Weighted Moving Average """
        if not length:
            length = self.p['vwma_length']

        s1 = self.talib_s(talib.SMA, ss * vol, length)
        s2 = self.talib_s(talib.SMA, vol, length)
        return s1 / s2

    def vwma_sig(self, ohlcv):
        vwma = self.vwma(ohlcv.close, ohlcv.volume)

        rise_sig = (vwma.shift(2) >= vwma.shift(1)) & (vwma.shift(1) < vwma)
        drop_sig = (vwma.shift(2) <= vwma.shift(1)) & (vwma.shift(1) > vwma)

        conf = pd.Series(index=ohlcv.index)
        conf[rise_sig.index[rise_sig == True]] = BUY * self.p['vwma_conf']
        conf[drop_sig.index[drop_sig == True]] = SELL * self.p['vwma_conf']

        self.verify_confidence(conf)
        self.cap_confidence(conf)

        return conf

    def vwma_ma(self, ss, vol, vwma_length=None, ma='wma', ma_length=None):
        if not ma_length:
            ma_length = self.p['vwma_ma_length']

        MA = getattr(talib, ma.upper())
        vwma = self.vwma(ss, vol, vwma_length)
        return self.talib_s(MA, vwma, ma_length)

    def vwma_ma_sig(self, ohlcv):
        vwma_ma = self.vwma_ma(ohlcv.close, ohlcv.volume, ma='ema')

        rise_sig = (vwma_ma.shift(2) >= vwma_ma.shift(1)) & (vwma_ma.shift(1) < vwma_ma)
        drop_sig = (vwma_ma.shift(2) <= vwma_ma.shift(1)) & (vwma_ma.shift(1) > vwma_ma)

        conf = pd.Series(index=ohlcv.index)
        conf[rise_sig.index[rise_sig == True]] = BUY * self.p['vwma_ma_conf']
        conf[drop_sig.index[drop_sig == True]] = SELL * self.p['vwma_ma_conf']

        self.verify_confidence(conf)
        self.cap_confidence(conf)

        return conf

    def dmi(self, ohlcv, adx_length=None, di_length=None):
        """ Directional Moving Average, consists of ADX, +DI and -DI """
        if not adx_length:
            adx_length = self.p['dmi_adx_length']
        if not di_length:
            di_length = self.p['dmi_di_length']

        low = ohlcv.low
        high = ohlcv.high
        close = ohlcv.close
        EMA = talib.EMA

        up = ohlcv.high - ohlcv.shift(1).high
        down = -(ohlcv.low - ohlcv.shift(1).low)

        pdm = pd.Series(0, index=ohlcv.index)
        mdm = pd.Series(0, index=ohlcv.index)
        di_sum = pd.Series(1, index=ohlcv.index)

        pdm[(up > down) & (up > 0)] = up
        mdm[(up < down) & (down > 0)] = down

        truerange = pd.concat([high - low, np.abs(high - close.shift(1)), np.abs(low - close.shift(1))], axis=1).max(axis=1)
        truerange = self.talib_s(EMA, truerange, di_length)
        pdi = 100 * self.talib_s(EMA, pdm, di_length) / truerange
        mdi = 100 * self.talib_s(EMA, mdm, di_length) / truerange
        di_sum[(pdi + mdi) != 0] = (pdi + mdi)
        adx = 100 * self.talib_s(EMA, np.abs(pdi - mdi) / (di_sum), adx_length)

        return adx, pdi, mdi

    def dmi_sig(self, ohlcv):
        # Parameters
        base_thresh = self.p['dmi_base_thresh']
        adx_thresh = self.p['dmi_adx_thresh']
        di_top_thresh = self.p['dmi_di_top_thresh']
        di_bot_thresh = self.p['dmi_di_bot_thresh']

        adx_top_peak_diff = self.p['dmi_adx_top_peak_diff']
        adx_bot_peak_diff = self.p['dmi_adx_bot_peak_diff']
        di_diff = self.p['dmi_di_diff']

        ema_length = self.p['dmi_ema_length']
        rsi_length = self.p['dmi_rsi_length']

        stochrsi_length = self.p['dmi_stochrsi_length']
        stoch_length = self.p['dmi_stoch_length']
        fk_length = self.p['dmi_slowk_length']
        fd_length = self.p['dmi_slowd_length']

        # Indicators
        adx, pdi, mdi = self.dmi(ohlcv)
        ema = self.talib_s(talib.EMA, ohlcv.close, ema_length)
        rsi = self.talib_s(talib.RSI, ohlcv.close, rsi_length)
        mom = self.mom(ohlcv.close, ma='wma', normalize=True)
        k, d = self.stoch_rsi(
            ohlcv.close,
            stochrsi_length,
            stoch_length,
            fk_length,
            fd_length)

        midzr = self.p['dmi_mom_mid_zone_range']
        mom_mid_zone = (mom < midzr) & (mom > -midzr)

        # Calculate top_peak and bot_peak
        top_peak = pd.Series(np.nan, index=adx.index)
        bot_peak = pd.Series(np.nan, index=adx.index)

        for i in range(len(adx)):
            if (adx.iloc[i] < adx.shift(1).iloc[i]) & (adx.shift(1).iloc[i] > adx.shift(2).iloc[i]):
                top_peak.iloc[i] = adx.shift(1).iloc[i]
            else:
                top_peak.iloc[i] = top_peak.shift(1).iloc[i]

            if (adx.iloc[i] > adx.shift(1).iloc[i]) & (adx.shift(1).iloc[i] < adx.shift(2).iloc[i]):
                bot_peak.iloc[i] = adx.shift(1).iloc[i]
            else:
                bot_peak.iloc[i] = bot_peak.shift(1).iloc[i]

        # Calculate top_peak_trend and bot_peak_trend
        top_peak_trend = pd.Series(np.nan, index=adx.index)
        bot_peak_trend = pd.Series(np.nan, index=adx.index)

        for i in range(len(adx)):
            if (adx.iloc[i] < adx.shift(1).iloc[i]) & (adx.shift(1).iloc[i] > adx.shift(2).iloc[i]):
                top_peak_trend.iloc[i] = 1 if pdi.shift(1).iloc[i] > mdi.shift(1).iloc[i] else -1
            else:
                top_peak_trend.iloc[i] = top_peak_trend.shift(1).iloc[i]

            if (adx.iloc[i] > adx.shift(1).iloc[i]) & (adx.shift(1).iloc[i] < adx.shift(2).iloc[i]):
                bot_peak_trend.iloc[i] = 1 if pdi.shift(1).iloc[i] > mdi.shift(1).iloc[i] else -1
            else:
                bot_peak_trend.iloc[i] = bot_peak_trend.shift(1).iloc[i]

        top_peak_diff = top_peak - adx_top_peak_diff
        bot_peak_diff = bot_peak + adx_bot_peak_diff

        # adx_reverse = (adx <= top_peak_diff) & (adx > adx_thresh + 5)
        # adx_rebound = (adx >= bot_peak_diff) & (adx < adx_thresh + 10)
        adx_reverse = (adx <= top_peak_diff) & (adx.shift(1) > top_peak_diff) & (adx > adx_thresh + 5)
        adx_rebound = (adx >= bot_peak_diff) & (adx.shift(1) < bot_peak_diff) & (adx < adx_thresh + 10)

        # for i in range(len(adx_rebound)):
        #     if np.isnan(adx_rebound.iloc[i]) \
        #     and (not (adx_rebound[max(i-2, 0):i]).all

        # TODO: extend adx_rebound for 2-3 bars

        match_base_thresh = adx >= base_thresh
        match_adx_thresh = adx >= adx_thresh
        match_di_top_thresh = (pdi >= di_top_thresh) | (mdi >= di_top_thresh)
        match_di_diff = np.abs(pdi - mdi) >= di_diff
        cross_base_thresh = (adx.shift(1) < base_thresh) & (adx >= base_thresh)

        below_base = (adx.shift(1) >= base_thresh) & ~match_base_thresh
        no_trend = ~match_adx_thresh & ~match_di_top_thresh

        buy  = (pdi > mdi) & (adx_rebound | cross_base_thresh) & match_base_thresh & ~no_trend
        sell = (pdi < mdi) & (adx_rebound | cross_base_thresh) & match_base_thresh & ~no_trend

        buy_reverse = (top_peak_trend == -1) & (pdi > di_bot_thresh) & adx_reverse & match_adx_thresh & match_base_thresh & ~no_trend
        sell_reverse = (top_peak_trend == 1) & (mdi > di_bot_thresh) & adx_reverse & match_adx_thresh & match_base_thresh & ~no_trend

        buy_di_turn  = (pdi > mdi) & (pdi.shift(1) < mdi.shift(1)) & (pdi > di_top_thresh) & match_base_thresh & ~no_trend
        sell_di_turn = (pdi < mdi) & (pdi.shift(1) > mdi.shift(1)) & (mdi > di_top_thresh) & match_base_thresh & ~no_trend

        ema_up = ema > ema.shift(1)
        ema_down = ema < ema.shift(1)

        rsi_buy = ((rsi <= 25) & (mom <= -self.p['dmi_rsi_mom_thresh'])) & ~(mdi > adx)# | (rsi <= 15)
        rsi_sell = ((rsi >= 80) & (mom >= self.p['dmi_rsi_mom_thresh'])) & ~(pdi > adx)# | (rsi >= 85)

        stoch_rsi_close = (((k > 90) & (rsi > 70) & (k < k.shift(1))) | ((k < 10) & (rsi < 30) & (k > k.shift(1))))

        buy_sig = (((buy | buy_reverse | buy_di_turn) & ema_up) | (rsi_buy & ema_down))# & ~(d >= 65)
        sell_sig = (((sell | sell_reverse | sell_di_turn) & ema_down) | (rsi_sell & ema_up))# & ~(d <= 35)
        close_sig = below_base | no_trend | stoch_rsi_close

        sig = pd.Series(np.nan, index=ohlcv.index)
        sig[buy_sig == True] = 1
        sig[sell_sig == True] = -1
        sig[close_sig == True] = 0
        sig = self.clean_repeat_sig(sig)

        conf = pd.Series(np.nan, index=ohlcv.index)
        conf[sig == 1] = self.p['dmi_conf']
        conf[sig == -1] = -self.p['dmi_conf']
        conf[sig == 0] = 0

        return conf

    def mom(self, ss, length=None, ma='wma', ma_length=None, normalize=False):
        """ Momentum """
        if not length:
            length = self.p['mom_length']
        if not ma_length:
            ma_length = self.p['mom_ma_length']

        # mom = self.talib_s(talib.MOM, ss, length)
        mom = ss - ss.shift(int(length))

        if ma:
            MA = getattr(talib, ma.upper())
            mom = self.talib_s(MA, mom, ma_length)

        if normalize:
            mom = mom / ss * 100

        return mom

    def mom_sig(self, ohlcv):
        past_length = 90 # previous N bars to find high low
        norm = True

        if len(ohlcv) < past_length:
            raise ValueError('mom_sig requires at least 90 bars of ohlcv')

        if norm:
            mid_zone_range = self.p['mom_norm_mid_zone_range']
        else:
            mid_zone_range = self.p['mom_mid_zone_percent']

        mom = self.mom(ohlcv.close, normalize=norm)
        mom = self.hma(mom, length=self.p['mom_second_ma_length'])

        mom_mid_zone = pd.Series(np.nan, index=ohlcv.index, dtype=bool)
        for i in range(past_length, len(mom)):
            high = mom[max(i-past_length, 0):i].max()
            low = mom[max(i-past_length, 0):i].min()
            mom_mid_zone.iloc[i] = (mom.iloc[i] / (high-low)) < mid_zone_range

        mom_peak = ((mom > mom[1]) & (mom[1] < mom[2])) | ((mom < mom[1]) & (mom[1] > mom[2]))
        buy_sig = (mom > mom.shift(1))
        sell_sig = (mom < mom.shift(1))
        close_sig = mom_mid_zone & mom_peak

        sig = pd.Series(np.nan, index=ohlcv.index)
        sig[buy_sig == True] = 1
        sig[sell_sig == True] = -1
        sig[close_sig == True] = 0
        sig = self.clean_repeat_sig(sig)

        conf = pd.Series(np.nan, index=ohlcv.index)
        conf[sig == 1] = self.p['mom_conf']
        conf[sig == -1] = -self.p['mom_conf']
        conf[sig == 0] = 0

        return conf

    def stoch_rsi(self, ss, rsi_length=None, stoch_length=None, slowk_length=None, slowd_length=None, ma='sma'):
        if not rsi_length:
            rsi_length = self.p['stochrsi_length']
        if not stoch_length:
            stoch_length = self.p['stoch_length']
        if not slowk_length:
            slowk_length = self.p['stochrsi_slowk_length']
        if not slowd_length:
            slowd_length = self.p['stochrsi_slowd_length']

        rsi = self.talib_s(talib.RSI, ss, rsi_length)

        fastk, fastd = self.talib_s(
            talib.STOCH, rsi,
            np.asarray(rsi),
            np.asarray(rsi),
            fastk_period=stoch_length,
            slowk_period=slowk_length,
            slowd_period=slowd_length)

        return fastk, fastd

    def stoch_rsi_sig(self, ohlcv):
        stochrsi_upper = self.p['stochrsi_upper']
        stochrsi_lower = self.p['stochrsi_lower']

        adx_length = self.p['stochrsi_adx_length']
        di_length = self.p['stochrsi_di_length']

        rsi_length = self.p['stochrsi_rsi_length']
        rsi_mom_thresh = self.p['stochrsi_rsi_mom_thresh']
        rsi_upper = self.p['stochrsi_rsi_upper']
        rsi_lower = self.p['stochrsi_rsi_lower']

        mom_length = self.p['stochrsi_mom_length']
        mom_ma_length = self.p['stochrsi_mom_ma_length']

        # Indicators
        adx, pdi, mdi = self.dmi(ohlcv, adx_length, di_length)
        k, d = self.stoch_rsi(ohlcv.close)
        rsi = self.talib_s(talib.RSI, ohlcv.close, rsi_length)
        mom = self.mom(ohlcv.close, mom_length, ma_length=mom_ma_length, normalize=True)

        src = k

        top_peak = pd.Series(np.nan, index=src.index)
        bot_peak = pd.Series(np.nan, index=src.index)

        for i in range(len(src)):
            if (src.iloc[i] < src.shift(1).iloc[i]) and (src.shift(1).iloc[i] > src.shift(2).iloc[i]):
                top_peak.iloc[i] = src.shift(1).iloc[i]
            else:
                top_peak.iloc[i] = top_peak.shift(1).iloc[i]

            if (src.iloc[i] > src.shift(1).iloc[i]) and (src.shift(1).iloc[i] < src.shift(2).iloc[i]):
                bot_peak.iloc[i] = src.shift(1).iloc[i]
            else:
                bot_peak.iloc[i] = bot_peak.shift(1).iloc[i]

        stochrsi_buy = (src.shift(1) < stochrsi_lower) & (src >= stochrsi_lower)
        stochrsi_sell = (src.shift(1) > stochrsi_upper) & (src <= stochrsi_upper)

        stochrsi_rebuy = (src.shift(1) < stochrsi_upper) & (src >= stochrsi_upper) & (bot_peak > stochrsi_lower)
        stochrsi_resell = (src.shift(1) > stochrsi_lower) & (src <= stochrsi_lower) & (top_peak < stochrsi_upper)

        rsi_buy = ((rsi <= rsi_upper) & (mom <= -rsi_mom_thresh)) & ~(mdi > adx) # or (rsi <= 10)
        rsi_sell = ((rsi >= rsi_lower) & (mom >= rsi_mom_thresh)) & ~(pdi > adx) # or (rsi >= 90)

        stoch_rsi_close = pd.Series(False, index=src.index)

        buy_sig = stochrsi_buy | stochrsi_rebuy | rsi_buy
        sell_sig = stochrsi_sell | stochrsi_resell | rsi_sell
        close_sig = stoch_rsi_close

        sig = pd.Series(np.nan, index=ohlcv.index)
        sig[buy_sig == True] = 1
        sig[sell_sig == True] = -1
        sig[close_sig == True] = 0
        sig = self.clean_repeat_sig(sig)

        conf = pd.Series(np.nan, index=ohlcv.index)
        conf[sig == 1] = self.p['stochrsi_conf']
        conf[sig == -1] = -self.p['stochrsi_conf']
        conf[sig == 0] = 0

        return conf

    ############################################################################

    @staticmethod
    def last_peak(ss):
        """ Calculate last peak value. """
        peak = pd.Series(np.nan, index=ss.index)

        for i in range(1, len(ss)):
            if ss.iloc[i] < ss.shift(1).iloc[i] \
            and ss.shift(1).iloc[i] > ss.shift(2).iloc[i]:
                peak.iloc[i] = ss.shift(1).iloc[i]
            else:
                peak.iloc[i] = peak.shift(1).iloc[i]

        return peak

    @staticmethod
    def talib_s(indicator, input, *args, **kwargs):
        """ Covert pd.Series to talib function compatible format,
            apply, and then convert back to pd.Series.
        """
        res = []
        ss = indicator(np.asarray(input), *args, **kwargs)
        if (isinstance(ss, tuple) or isinstance(ss, list)) \
        and len(ss) > 1:
            for s in ss:
                tmp = pd.Series(s, index=input.index)
                res.append(tmp)
        else:
            res = pd.Series(ss, index=input.index)

        return res

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
    def clean_repeat_sig(sig):
        """ Clean repeated signals, keep the first one. """
        sig = sig.copy()
        last_sig = None

        for i in range(len(sig)):
            if last_sig == sig.iloc[i] or np.isnan(sig.iloc[i]):
                sig.iloc[i] = np.nan
            else:
                last_sig = sig.iloc[i]

        return sig


##################################
# PINE SCRIPT BUILT-IN FUNCTIONS #
##################################

def highest(ss, n):
    """ Highest value for a given number of bars back. """
    tmp = pd.Series(index=ss.index)
    for i in np.arange(len(ss)):
        m = max(0, i+0-n)
        tmp[i] = ss[m:i+0].max()
    return tmp

def lowest(ss, n):
    """ Lowest value for a given number of bars back. """
    tmp = pd.Series(index=ss.index)
    for i in np.arange(len(ss)):
        m = max(0, i+0-n)
        tmp[i] = ss[m:i+0].min()
    return tmp

def stdev(ss, n):
    """ Standard deviation of max last n elements in a series. """
    tmp = pd.Series(index=ss.index)
    for i in np.arange(len(ss)):
        m = max(0, i+0-n)
        tmp[i] = np.std(ss[m:i+0])
    return tmp


def nz(ss):
    """ Convert NaN to 0 for pd.Series or a single value. """
    if isinstance(ss, pd.Series):
        ss[np.isnan(ss)] = 0
    elif isinstance(ss, float): # np.nan is a float
        ss = 0 if np.isnan(ss) else ss
    return ss


def na(ss):
    """ Convert 0 to NaN for pd.Series or a single value. """
    if isinstance(ss, pd.Series):
        ss[ss == 0] = np.nan
    elif isinstance(ss, int) or isinstance(ss, float):
        ss = np.nan if ss == 0 else ss
    return ss

###################################
# END END END END END END END END #
###################################

def plot(ss):
    ss.plot()
    plt.show()
