//@version=3
strategy("StochRSI Strategy", pyramiding=0, default_qty_type=strategy.percent_of_equity, default_qty_value=90, commission_type=strategy.commission.percent, commission_value=0.3)

//////////////////////////////////////////////////////////////////////
// Component Code Start
testStartYear = input(2018, "Backtest Start Year")
testStartMonth = input(1, "Backtest Start Month")
testStartDay = input(1, "Backtest Start Day")
testPeriodStart = timestamp(testStartYear,testStartMonth,testStartDay,0,0)

testStopYear = input(2019, "Backtest Stop Year")
testStopMonth = input(1, "Backtest Stop Month")
testStopDay = input(1, "Backtest Stop Day")
testPeriodStop = timestamp(testStopYear,testStopMonth,testStopDay,0,0)

// A switch to control background coloring of the test period89-=
testPeriodBackgroundColor = (time >= testPeriodStart) and (time <= testPeriodStop) ? #00FF00 : na
bgcolor(testPeriodBackgroundColor, transp=97)

testPeriod() =>
    time >= testPeriodStart and time <= testPeriodStop ? true : false
// Component Code Stop
//////////////////////////////////////////////////////////////////////

ADX(dilen, adxlen) =>
    up = change(high)
    down = -change(low)
    truerange = ema(tr, dilen)
    pdi = fixnan(100 * ema(up > down and up > 0 ? up : 0, dilen) / truerange)
    mdi = fixnan(100 * ema(down > up and down > 0 ? down : 0, dilen) / truerange)
    adx = 100 * ema(abs(pdi - mdi) / ((pdi + mdi) == 0 ? 1 : (pdi + mdi)), adxlen)
    [adx, pdi, mdi]

STOCHRSI(src, rsilen, stochlen, klen, dlen) =>
    rsi = rsi(src, rsilen)
    k = sma(stoch(rsi, rsi, rsi, stochlen), klen)
    d = sma(k, dlen)
    [k, d]

NORM_MOM(src, momlen, malen) =>
    // mom = mom(src, momlen)
    mom = src - src[momlen]
    mom := wma(mom, malen)
    norm_mom = mom / src * 100

use_k = input(defval=true, type=bool, title="Use K as signal source")
stochrsi_length = input(18, title="Stoch RSI Length")
stoch_length = input(10, title="Stoch Length")
k_length = input(2, title="Stoch K Length")
d_length = input(2, title="Stoch D Length")
stochrsi_upper = input(70, title="StochRSI Upper Threshold")
stochrsi_lower = input(35, title="StochRSI Lower Threshold")

adxlen = input(30, title="ADX Length")
dilen = input(12, title="DI Length")

rsi_length = input(14, title="RSI Length")
rsi_upper = input(80, title="RSI Uppper Threshold")
rsi_lower = input(25, title="RSI Lower Threshold")
rsi_mom_thresh = input(20, title="RSI Momentum Threshold")

mom_length = input(20, title="Momentum Length")
mom_ma_length = input(10, title="Momentum MA Length")

[adx, pdi, mdi] = ADX(dilen, adxlen)
[k, d] = STOCHRSI(close, stochrsi_length, stoch_length, k_length, d_length)
rsi = rsi(close, rsi_length)
mom = NORM_MOM(close, mom_length, mom_ma_length)

src = use_k ? k : d

top_peak = na
bot_peak = na
top_peak := (src < src[1]) and (src[1] > src[2]) ? src[1] : top_peak[1]
bot_peak := (src > src[1]) and (src[1] < src[2]) ? src[1] : bot_peak[1]

stochrsi_buy = (src[1] < stochrsi_lower) and (src >= stochrsi_lower)
stochrsi_sell = (src[1] > stochrsi_upper) and (src <= stochrsi_upper)

stochrsi_rebuy = (src[1] < stochrsi_upper) and (src >= stochrsi_upper) and (bot_peak > stochrsi_lower)
stochrsi_resell = (src[1] > stochrsi_lower) and (src <= stochrsi_lower) and (top_peak < stochrsi_upper)

rsi_buy = ((rsi <= rsi_lower) and (mom <= -rsi_mom_thresh)) and not (mdi > adx)
rsi_sell = ((rsi >= rsi_upper) and (mom >= rsi_mom_thresh)) and not (pdi > adx)

buy_sig = stochrsi_buy or stochrsi_rebuy or rsi_buy
sell_sig = stochrsi_sell or stochrsi_resell or rsi_sell
close_sig = false


sig = na
sig := close_sig ? 0 : buy_sig ? 1 : sell_sig ? -1 : sig[1]

long  = (sig == 1) ? true : false
short = (sig == -1) ? true : false
exit = (sig == 0) ? true : false

if (long and testPeriod())
    strategy.entry("buy", strategy.long)

if (short and testPeriod())
    strategy.entry("sell", strategy.short)

if (exit and testPeriod())
    strategy.close_all(when=close_sig)


hline(stochrsi_upper, color=blue)
hline(stochrsi_lower, color=blue)
plot(k, color=red, title="k-line", linewidth=1)
plot(d, color=fuchsia, title="d-line", linewidth=1)
plot(src, color=fuchsia, title="src-line", linewidth=3)

plot(stochrsi_buy ? 3 : 0)