//@version=3
strategy("StochRSI BBFib Strategy", pyramiding=0, overlay=true, default_qty_type=strategy.percent_of_equity, default_qty_value=90, commission_type=strategy.commission.percent, commission_value=0.3)

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

rsi_length = input(14, title="RSI Length")
rsi_upper = input(80, title="RSI Uppper Threshold")
rsi_lower = input(25, title="RSI Lower Threshold")
rsi_mom_thresh = input(20, title="RSI Momentum Threshold")

mom_length = input(20, title="Momentum Length")
mom_ma_length = input(10, title="Momentum MA Length")

bb_len = input(defval=16, minval=1, title="Bollinger Band Length")
fib1 = input(defval=1.618, title="Fibonacci Ratio 1")
fib2 = input(defval=2.618, title="Fibonacci Ratio 2")
fib3 = input(defval=4.618, title="Fibonacci Ratio 3")
ma_short_len = input(defval=5, title="MA Short Length")
ma_long_len = input(defval=90, title="MA Long Length")
exponential = input(true, title="Use Exponential MA")
roc_len = input(defval=6, title="Rate of Change Length")

kama_len = input(21, minval=1, title="Kaufman Adaptive Moving Average Length")

val = input(defval=1.0, title="Plotting max height")

//////////////////////////////////////////////////////////////////////

// Indicator
src = close

[adx, pdi, mdi] = ADX(dilen, adxlen)
[k, d] = STOCHRSI(src, stochrsi_length, stoch_length, k_length, d_length)
rsi = rsi(src, rsi_length)
mom = NORM_MOM(src, mom_length, mom_ma_length)
bb_ma = sma(src, bb_len)
bb_avg = RMA(TRUE_RANGE(high, low, close), bb_len)
ma_short = exponential ? ema(src, ma_short_len) : sma(src, ma_short_len)
ma_long = exponential ? ema(src, ma_long_len) : sma(src, ma_long_len)

stoch_src = use_k ? k : d

top_peak = na
bot_peak = na
top_peak := (stoch_src < stoch_src[1]) and (stoch_src[1] > stoch_src[2]) ? stoch_src[1] : top_peak[1]
bot_peak := (stoch_src > stoch_src[1]) and (stoch_src[1] < stoch_src[2]) ? stoch_src[1] : bot_peak[1]

r1 = bb_avg*fib1
r2 = bb_avg*fib2
r3 = bb_avg*fib3
top3 = bb_ma+r3
top2 = bb_ma+r2
top1 = bb_ma+r1
bot1 = bb_ma-r1
bot2 = bb_ma-r2
bot3 = bb_ma-r3
topmid1 = (bb_ma + top1) / 2
topmid2 = (top1 + top2) / 2
topmid3 = (top2 + top3) / 2
botmid1 = (bb_ma + bot1) / 2
botmid2 = (bot1 + bot2) / 2
botmid3 = (bot2 + bot3) / 2

roc = ROC(src, roc_len)
chg = min(roc / 2, 5) // limit chg to max 5
chg := max(chg, 2) // limit chg to min 2
chg := chg / 100

xvnoise = abs(src - src[1])
nfastend = 0.666
nslowend = 0.0645
nsignal = abs(src - src[kama_len])
nnoise = sum(xvnoise, kama_len)
nefratio = nnoise != 0 ? nsignal / nnoise : 0
nsmooth = pow(nefratio * (nfastend - nslowend) + nslowend, 2)
nAMA = nz(nAMA[1]) + nsmooth * (src - nz(nAMA[1]))

//////////////////////////////////////////////////////////////////////

// Strategy
ma_short_turn_up = (src > ma_short) and (src - ma_short) / src > chg
ma_short_turn_down = (src < ma_short) and (src - ma_short) / src < -chg

ma_long_turn_up = (src > ma_long) and (src - ma_long) / src > chg
ma_long_turn_down = (src < ma_long) and (src - ma_long) / src < -chg

ma_short_up = src > src[1]
ma_short_down = src < src[1]

bb_ma_up = bb_ma > bb_ma[1]
bb_ma_down = bb_ma < bb_ma[1]

stochrsi_buy = (stoch_src[1] < stochrsi_lower) and (stoch_src >= stochrsi_lower)
stochrsi_sell = (stoch_src[1] > stochrsi_upper) and (stoch_src <= stochrsi_upper)

stochrsi_rebuy = (stoch_src[1] < stochrsi_upper) and (stoch_src >= stochrsi_upper) and (bot_peak > stochrsi_lower)
stochrsi_resell = (stoch_src[1] > stochrsi_lower) and (stoch_src <= stochrsi_lower) and (top_peak < stochrsi_upper)

rsi_buy = ((rsi <= rsi_lower) and (mom <= -rsi_mom_thresh)) and not (mdi > adx)
rsi_sell = ((rsi >= rsi_upper) and (mom >= rsi_mom_thresh)) and not (pdi > adx)

stochrsi_bb = (stochrsi_buy or stochrsi_rebuy) and (not (bb_ma_down and src > botmid2))
stochrsi_ss = (stochrsi_sell or stochrsi_resell) and (not (bb_ma_up and src < topmid2))

buy_sig = stochrsi_bb or rsi_buy
sell_sig = stochrsi_ss or rsi_sell
close_sig = na

///////////////////////////////////////////////////////////////////////////////

// Trade
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
leadMAColor(ma, src) =>
    color = src > ma ? lime : red

trendColor(src) =>
    color = src > src[1] ? lime : red

plot( ma_short, color=leadMAColor(ma_short, src), style=line, title="MMA_short", linewidth=3)
plot( ma_long, color=leadMAColor(ma_long, src), style=line, title="MMA_long", linewidth=3)

t3=plot(top3,transp=0,title="Upper 3",color=teal)
t2=plot(top2,transp=20,title="Upper 2",color=teal)
t1=plot(top1,transp=40,title="Upper 1",color=teal)
b1=plot(bot1,transp=40,title="Lower 1",color=teal)
b2=plot(bot2,transp=20,title="Lower 2",color=teal)
b3=plot(bot3,transp=0,title="Lower 3",color=teal)
plot(bb_ma,title="SMA",color=trendColor(bb_ma))
fill(t3,b3,color=navy,transp=90)

plot(not (bb_ma_down and src > botmid2) ? val : 0, linewidth=2, color=orange)
plot(not (bb_ma_up and src < topmid2) ? val : 0, linewidth=2, color=purple)
plot((stochrsi_buy or stochrsi_rebuy or rsi_buy) ? val/2 : 0, linewidth=2, color=lime)
plot((stochrsi_sell or stochrsi_resell or rsi_sell) ? val/2 : 0, linewidth=2, color=red)

plot(nAMA, color=blue, title="KAMA")
///////////////////////////////////////////////////////////////////////////////

// hline(stochrsi_upper, color=blue)
// hline(stochrsi_lower, color=blue)
// plot(k, color=red, title="k-line", linewidth=1)
// plot(d, color=fuchsia, title="d-line", linewidth=1)
// plot(src, color=fuchsia, title="src-line", linewidth=3)

