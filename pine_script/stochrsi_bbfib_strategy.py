//@version=3
strategy("StochRSI BBFib Strategy", pyramiding=0, overlay=true, default_qty_type=strategy.percent_of_equity, default_qty_value=90, commission_type=strategy.commission.percent, commission_value=0.5)

//////////////////////////////////////////////////////////////////////
// Component Code Start
testStartYear = input(2017, "Backtest Start Year")
testStartMonth = input(10, "Backtest Start Month")
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

RMA(x, y) =>
	alpha = y
    sum = 0.0
    sum := (x + (alpha - 1) * nz(sum[1])) / alpha

TRUE_RANGE(high, low, close) =>
    true_range = max(high - low, max(abs(high - close[1]), abs(low - close[1])))

ROC(src, len) =>
    roc = (src - src[len]) / src[len] * 100

NORM(src, len) =>
    norm = src / sum(abs(src), len) * len

KAMA(src, kama_len) =>
    xvnoise = abs(src - src[1])
    nfastend = 0.666
    nslowend = 0.0645
    nsignal = abs(src - src[kama_len])
    nnoise = sum(xvnoise, kama_len)
    nefratio = iff(nnoise != 0, nsignal / nnoise, 0)
    nsmooth = pow(nefratio * (nfastend - nslowend) + nslowend, 2)
    nAMA = na
    nAMA := nz(nAMA[1]) + nsmooth * (src - nz(nAMA[1]))

//////////////////////////////////////////////////////////////////////

// Parameter
use_k = input(defval=true, type=bool, title="Use K as signal source")
stochrsi_length = input(18, title="Stoch RSI Length")
stoch_length = input(10, title="Stoch Length")
k_length = input(2, title="Stoch K Length")
d_length = input(2, title="Stoch D Length")
stochrsi_upper = input(70, title="StochRSI Upper Threshold")
stochrsi_lower = input(35, title="StochRSI Lower Threshold")

adxlen = input(30, title="ADX Length")
dilen = input(12, title="DI Length")
adx_thresh = input(23, title="ADX Threshold")
adx_chg_len = input(3, title="ADX Chg Length")

rsi_length = input(14, title="RSI Length")
rsi_upper = input(85, title="RSI Uppper Threshold")
rsi_lower = input(25, title="RSI Lower Threshold")
rsi_mom_thresh = input(20, title="RSI Momentum Threshold")

mom_length = input(20, title="Momentum Length")
mom_ma_length = input(10, title="Momentum MA Length")

bb_len = input(defval=16, minval=1, title="Bollinger Band Length")
fib1 = input(defval=1.618, title="Fibonacci Ratio 1")
fib2 = input(defval=2.618, title="Fibonacci Ratio 2")
fib3 = input(defval=4.618, title="Fibonacci Ratio 3")
ma_long_len = input(defval=100,title="MA Long Length")
ma_mid_len = input(defval=50,title="MA Mid Length")
ma_short_len = input(defval=5,title="MA Short Length")
exponential = input(true, title="Use Exponential MA")

ma_long_chg_len = input(defval=3, title="MA Long Chg Length")
ma_long_chg_norm_len = input(defval=15, title="MA Long Chg Normalize Length")
ma_short_chg_norm_len = input(defval=15, title="MA Short Chg Normalize Length")
ma_long_chg_norm_chg_len = input(defval=5, title="MA Long Chg Normalize Chg Length")

kama_len = input(21, minval=1, title="KAMA Length")
kama_chg_avg_len = input(24, minval=1, title="KAMA Chg Avg Length")
kama_chg_avg_thresh = input(0.1, step=0.1, title="KAMA Chg Avg Threshold")

chg_scale = input(defval=1, step=0.1, title="Chg Scale")

//////////////////////////////////////////////////////////////////////

// Indicator
src = close

[adx, pdi, mdi] = ADX(dilen, adxlen)
[k, d] = STOCHRSI(src, stochrsi_length, stoch_length, k_length, d_length)
rsi = rsi(src, rsi_length)
mom = NORM_MOM(src, mom_length, mom_ma_length)
mid = sma(src, bb_len)
bb_avg = RMA(TRUE_RANGE(high, low, close), bb_len)
kama = KAMA(src, kama_len)

stoch_src = use_k ? k : d

top_peak = na
bot_peak = na
top_peak := (stoch_src < stoch_src[1]) and (stoch_src[1] > stoch_src[2]) ? stoch_src[1] : top_peak[1]
bot_peak := (stoch_src > stoch_src[1]) and (stoch_src[1] < stoch_src[2]) ? stoch_src[1] : bot_peak[1]

r1 = bb_avg*fib1
r2 = bb_avg*fib2
r3 = bb_avg*fib3
top3 = mid+r3
top2 = mid+r2
top1 = mid+r1
bot1 = mid-r1
bot2 = mid-r2
bot3 = mid-r3
topmid1 = (mid + top1) / 2
topmid2 = (top1 + top2) / 2
topmid3 = (top2 + top3) / 2
botmid1 = (mid + bot1) / 2
botmid2 = (bot1 + bot2) / 2
botmid3 = (bot2 + bot3) / 2

ma_long = exponential ? ema(src, ma_long_len) : sma(src, ma_long_len)
ma_mid = exponential ? ema(src, ma_mid_len) : sma(src, ma_mid_len)
ma_short = exponential ? ema(src, ma_short_len) : sma(src, ma_short_len)

ma_long_chg = (ma_long - ma_long[ma_long_chg_len]) / ma_long * 100
ma_long_chg_norm = NORM(ma_long_chg, ma_long_chg_norm_len)
ma_long_chg_norm := abs(ma_long_chg_norm) < abs(ma_long_chg) ? ma_long_chg_norm : ma_long_chg
ma_long_chg_norm_chg = (ma_long_chg_norm - ma_long_chg_norm[ma_long_chg_norm_chg_len])

// plot(ma_long_chg * chg_scale, linewidth=1, color=orange)
// plot(ma_long_chg_norm * chg_scale, linewidth=2, color=red)
// plot(ma_long_chg_norm_chg * chg_scale, linewidth=1, color=purple)

ma_short_chg = (ma_short - ma_short[ma_long_chg_len]) / ma_short * 100
ma_short_chg_norm = NORM(ma_short_chg, ma_short_chg_norm_len)
ma_short_chg_norm := abs(ma_short_chg_norm) < abs(ma_short_chg) ? ma_short_chg_norm : ma_short_chg
ma_short_chg_norm_chg = (ma_short_chg_norm - ma_short_chg_norm[ma_long_chg_norm_chg_len])

plot(ma_short_chg * chg_scale, linewidth=1, color=navy)
plot(ma_short_chg_norm * chg_scale, linewidth=2, color=blue)
plot(ma_short_chg_norm_chg * chg_scale, linewidth=1, color=aqua)

adx_pdi_up = (pdi > mdi and adx > adx[1])
adx_pdi_down = (pdi > mdi and adx < adx[1])
adx_mdi_up = (mdi > pdi and adx > adx[1])
adx_mdi_down = (mdi > pdi and adx < adx[1])
adx_up   = (pdi > mdi and adx > adx[1]) or (mdi > pdi and adx < adx[1])
adx_down = (pdi > mdi and adx < adx[1]) or (mdi > pdi and adx > adx[1])
adx_match_thresh = adx >= adx_thresh
adx_chg = (adx - adx[adx_chg_len]) / adx * 100

// plotshape(adx_up, style=shape.flag, location=location.abovebar, color=orange)
// plotshape(adx_down, style=shape.flag, location=location.abovebar, color=black)

kama_chg = (kama - kama[1]) / kama[1] * 100
kama_chg_avg = sum(kama_chg, kama_chg_avg_len) / kama_chg_avg_len

plot(kama, color=blue, linewidth=1, title="KAMA")
plot(kama_chg * chg_scale, color=gray, linewidth=2, title="KAMA Chg")
plot(kama_chg_avg * chg_scale, color=black, linewidth=1, title="KAMA Chg Avg")


//////////////////////////////////////////////////////////////////////

// Strategy

mid_up = mid > mid[1]
mid_down = mid < mid[1]

stochrsi_buy = (stoch_src[1] < stochrsi_lower) and (stoch_src >= stochrsi_lower)
stochrsi_sell = (stoch_src[1] > stochrsi_upper) and (stoch_src <= stochrsi_upper)

stochrsi_rebuy = (stoch_src[1] < stochrsi_upper) and (stoch_src >= stochrsi_upper) and (bot_peak > stochrsi_lower)
stochrsi_resell = (stoch_src[1] > stochrsi_lower) and (stoch_src <= stochrsi_lower) and (top_peak < stochrsi_upper)

rsi_buy = ((rsi <= rsi_lower) and (mom <= -rsi_mom_thresh)) and not (mdi > adx)
rsi_sell = ((rsi >= rsi_upper) and (mom >= rsi_mom_thresh)) and not (pdi > adx)

bbfib_high = ((0 < ma_short_chg_norm and ma_short_chg_norm <= 0.7 and close > topmid2)
             or (0.7 < ma_short_chg_norm and ma_short_chg_norm <= 1 and close > topmid3)
             or (1 < ma_short_chg_norm and ma_short_chg_norm <= 1.5 and close > topmid3)
             or (1.5 < ma_short_chg_norm and ma_short_chg_norm <= 3 and (close > top3 or rsi >= 85))
             or (0 > ma_short_chg_norm and ma_short_chg_norm >= -0.5 and close > topmid1)
             or (-0.5 > ma_short_chg_norm and ma_short_chg_norm >= -1 and close > botmid1)
             or (-1 > ma_short_chg_norm and ma_short_chg_norm >= -3 and close > bot1)
             or (-3 > ma_short_chg_norm and close > botmid2)

bbfib_low = ((0 < ma_short_chg_norm and ma_short_chg_norm <= 0.7 and close < botmid1)
             or (0.7 < ma_short_chg_norm and ma_short_chg_norm <= 1 and close < topmid1)
             or (1 < ma_short_chg_norm and ma_short_chg_norm <= 1.5 and close < topmid1)
             or (1.5 < ma_short_chg_norm and ma_short_chg_norm <= 3 and close < top1)
             or (0 > ma_short_chg_norm and ma_short_chg_norm >= -0.5 and close < bot1)
             or (-0.5 > ma_short_chg_norm and ma_short_chg_norm >= -1 and close < botmid2)
             or (-1 > ma_short_chg_norm and ma_short_chg_norm >= -1.5 and close < botmid3)
             or (-1.5 > ma_short_chg_norm and ma_short_chg_norm >= -2 and close < bot3)

stochrsi_bb = (stochrsi_buy or stochrsi_rebuy) and not bbfib_high
stochrsi_ss = (stochrsi_sell or stochrsi_resell) and not bbfib_low

plot_stochrsi_bb = input(true, title="plot_stochrsi_bb")
plot_bbfib_high = plot_stochrsi_bb ? bbfib_high : na
plotshape(plot_bbfib_high, style=shape.xcross, location=location.belowbar, color=blue)
plot_stochrsi_buy = plot_stochrsi_bb ? stochrsi_buy : na
plotshape(plot_stochrsi_buy, style=shape.labelup, location=location.belowbar, color=orange)
plot_stochrsi_rebuy = plot_stochrsi_bb ? stochrsi_rebuy : na
plotshape(plot_stochrsi_rebuy, style=shape.labelup, location=location.belowbar, color=purple)
plot_rsi_buy = plot_stochrsi_bb ? rsi_buy : na
plotshape(plot_rsi_buy, style=shape.labelup, location=location.belowbar, color=green)

plot_stochrsi_ss = input(true, title="plot_stochrsi_ss")
plot_bbfib_low = plot_stochrsi_ss ? bbfib_low : na
plotshape(plot_bbfib_low, style=shape.xcross, location=location.abovebar, color=blue)
plot_stochrsi_sell = plot_stochrsi_ss ? stochrsi_sell : na
plotshape(plot_stochrsi_sell, style=shape.labeldown, location=location.abovebar, color=orange)
plot_stochrsi_resell = plot_stochrsi_ss ? stochrsi_resell : na
plotshape(plot_stochrsi_resell, style=shape.labeldown, location=location.abovebar, color=purple)
plot_rsi_sell = plot_stochrsi_ss ? rsi_sell : na
plotshape(plot_rsi_sell, style=shape.labeldown, location=location.abovebar, color=green)

buy_sig = na // stochrsi_bb or rsi_buy
sell_sig = na // stochrsi_ss or rsi_sell
close_sig = na

///////////////////////////////////////////////////////////////////////////////

// Trading
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

///////////////////////////////////////////////////////////////////////////////

// Plot

// Storchrsi
// hline(stochrsi_upper, color=blue)
// hline(stochrsi_lower, color=blue)
// plot(k, color=red, title="k-line", linewidth=1)
// plot(d, color=fuchsia, title="d-line", linewidth=1)

// BBFib
leadMAColor(ma, src) =>
    color = src > ma ? lime : red

plot(ma_short, color=leadMAColor(ma_short, src), style=line, title="MMA_short", linewidth=3)
plot(ma_mid, color=leadMAColor(ma_mid, src), style=line, title="MMA_mid", linewidth=3)
plot(ma_long, color=leadMAColor(ma_long, src), style=line, title="MMA_long", linewidth=3)

t3=plot(top3,transp=0,title="Upper 3",color=teal)
t2=plot(top2,transp=20,title="Upper 2",color=teal)
t1=plot(top1,transp=40,title="Upper 1",color=teal)
b1=plot(bot1,transp=40,title="Lower 1",color=teal)
b2=plot(bot2,transp=20,title="Lower 2",color=teal)
b3=plot(bot3,transp=0,title="Lower 3",color=teal)
bm1=plot(botmid1,transp=40,title="Lower 1",color=lime)
bm2=plot(botmid2,transp=20,title="Lower 2",color=lime)
bm3=plot(botmid3,transp=0,title="Lower 3",color=lime)
plot(mid,style=cross,title="SMA",color=teal)
fill(t3,b3,color=navy,transp=90)

///////////////////////////////////////////////////////////////////////////////
