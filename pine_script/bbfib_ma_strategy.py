//@version=3
strategy("BBFib MA Strategy", pyramiding=10, overlay=true, default_qty_type=strategy.percent_of_equity, default_qty_value=90, commission_type=strategy.commission.percent, commission_value=0.5)

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

// Parameter
bb_len = input(defval=20,minval=1)
fib1 = input(defval=1.618,title="Fibonacci Ratio 1")
fib2 = input(defval=2.618,title="Fibonacci Ratio 2")
fib3 = input(defval=4.618,title="Fibonacci Ratio 3")
ma_short_len = input(defval=5,title="MA Short Length")
ma_mid_len = input(defval=50,title="MA Mid Length")
ma_long_len = input(defval=100,title="MA Long Length")
exponential = input(true, title="Use Exponential MA")

rsi_length = input(14, title="RSI Length")
rsi_upper = input(85, title="RSI Uppper Threshold")
rsi_lower = input(25, title="RSI Lower Threshold")

adxlen = input(20, title="ADX Length")
dilen = input(20, title="DI Length")
adx_thresh = input(23, title="ADX Threshold")
adx_chg_len = input(3, title="ADX Chg Length")

ma_long_chg_len = input(defval=3, title="MA Long Chg Length")
ma_long_chg_norm_len = input(defval=15, title="MA Long Chg Normalize Length")
ma_short_chg_norm_len = input(defval=15, title="MA Short Chg Normalize Length")
ma_long_chg_norm_chg_len = input(defval=5, title="MA Long Chg Normalize Chg Length")

kama_len = input(21, minval=1, title="KAMA Length")
kama_chg_avg_len = input(24, minval=1, title="KAMA Chg Avg Length")
kama_chg_avg_thresh = input(0.1, step=0.1, title="KAMA Chg Avg Threshold")

chg_scale = input(defval=1, step=0.1, title="Chg Scale")

//////////////////////////////////////////////////////////////////////

RMA(x, y) =>
	alpha = y
    sum = 0.0
    sum := (x + (alpha - 1) * nz(sum[1])) / alpha

TRUE_RANGE(high, low, close) =>
    true_range = max(high - low, max(abs(high - close[1]), abs(low - close[1])))

ROC(src, len) =>
    roc = (src - src[len]) / src[len] * 100

SOFTMAX(src, len) =>
    src_exp = exp(src)
    softmax = sign(src) * src_exp / sum(src_exp, len)

NORM(src, len) =>
    norm = src / sum(abs(src), len) * len

ADX(dilen, adxlen) =>
    up = change(high)
    down = -change(low)
    truerange = ema(tr, dilen)
    pdi = fixnan(100 * ema(up > down and up > 0 ? up : 0, dilen) / truerange)
    mdi = fixnan(100 * ema(down > up and down > 0 ? down : 0, dilen) / truerange)
    adx = 100 * ema(abs(pdi - mdi) / ((pdi + mdi) == 0 ? 1 : (pdi + mdi)), adxlen)
    [adx, pdi, mdi]

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

// Indicator

src = close

rsi = rsi(close, rsi_length)
mid = sma(src, bb_len)
bb_avg = RMA(TRUE_RANGE(high, low, close), bb_len)
[adx, pdi, mdi] = ADX(dilen, adxlen)
kama = KAMA(src, kama_len)

r1 = bb_avg * fib1
r2 = bb_avg * fib2
r3 = bb_avg * fib3
top3 = mid + r3
top2 = mid + r2
top1 = mid + r1
bot1 = mid - r1
bot2 = mid - r2
bot3 = mid - r3
topmid3 = (top3 + top2) / 2
topmid2 = (top2 + top1) / 2
topmid1 = (top1 + mid) / 2
botmid1 = (bot1 + mid) / 2
botmid2 = (bot2 + bot1) / 2
botmid3 = (bot3 + bot2) / 2

ma_long = exponential ? ema(src, ma_long_len) : sma(src, ma_long_len)
ma_mid = exponential ? ema(src, ma_mid_len) : sma(src, ma_mid_len)
ma_short = exponential ? ema(src, ma_short_len) : sma(src, ma_short_len)

ma_long_chg = (ma_long - ma_long[ma_long_chg_len]) / ma_long * 100
ma_long_chg_norm = NORM(ma_long_chg, ma_long_chg_norm_len)
ma_long_chg_norm := abs(ma_long_chg_norm) < abs(ma_long_chg) ? ma_long_chg_norm : ma_long_chg
ma_long_chg_norm_chg = (ma_long_chg_norm - ma_long_chg_norm[ma_long_chg_norm_chg_len])

plot(ma_long_chg * chg_scale, linewidth=1, color=orange)
plot(ma_long_chg_norm * chg_scale, linewidth=2, color=red)
plot(ma_long_chg_norm_chg * chg_scale, linewidth=1, color=purple)

ma_short_chg = (ma_short - ma_short[ma_long_chg_len]) / ma_short * 100
ma_short_chg_norm = NORM(ma_short_chg, ma_short_chg_norm_len)
ma_short_chg_norm := abs(ma_short_chg_norm) < abs(ma_short_chg) ? ma_short_chg_norm : ma_short_chg
ma_short_chg_norm_chg = (ma_short_chg_norm - ma_short_chg_norm[ma_long_chg_norm_chg_len])

// plot(ma_short_chg * chg_scale, linewidth=1, color=navy)
// plot(ma_short_chg_norm * chg_scale, linewidth=2, color=blue)
// plot(ma_short_chg_norm_chg * chg_scale, linewidth=1, color=aqua)

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

// plot(kama, color=blue, linewidth=1, title="KAMA")
// plot(kama_chg * chg_scale, color=gray, linewidth=2, title="KAMA Chg")
// plot(kama_chg_avg * chg_scale, color=black, linewidth=1, title="KAMA Chg Avg")

///////////////////////////////////////////////////////////////////////////////

// Strategy

ma_long_chg_norm_pos_buy1 = (0 < ma_long_chg_norm and ma_long_chg_norm <= 0.3 and close < botmid1) and not (adx_chg < adx_chg[1]) // and not adx_pdi_down // and adx_match_thresh
ma_long_chg_norm_pos_buy2 = (0.3 < ma_long_chg_norm and ma_long_chg_norm <= 0.7 and close < topmid1) and not (adx_chg < adx_chg[1]) // and not adx_pdi_down // and adx_match_thresh
ma_long_chg_norm_pos_buy3 = (0.7 < ma_long_chg_norm and ma_long_chg_norm <= 1 and close < topmid1) and not (adx_chg < adx_chg[1]) // and not adx_pdi_down // and adx_match_thresh
ma_long_chg_norm_pos_buy4 = (1 < ma_long_chg_norm and ma_long_chg_norm <= 1.5 and close < topmid1) and not (adx_chg < adx_chg[1]) // and not adx_pdi_down // and adx_match_thresh
ma_long_chg_norm_pos_buy5 = (1.5 < ma_long_chg_norm and ma_long_chg_norm <= 3 and close < top1) and not (adx_chg < adx_chg[1]) // and not adx_pdi_down // and adx_match_thresh

ma_long_chg_norm_pos_sell_close1 = (0 < ma_long_chg_norm and ma_long_chg_norm <= 0.5 and low < mid)
ma_long_chg_norm_pos_sell_close2 = (0.5 < ma_long_chg_norm and ma_long_chg_norm <= 1 and low < topmid1)
ma_long_chg_norm_pos_sell_close3 = (1 < ma_long_chg_norm and ma_long_chg_norm <= 1.5 and low < top1)
ma_long_chg_norm_pos_sell_close4 = (1.5 < ma_long_chg_norm and low < topmid2)

ma_long_chg_norm_pos_sell1 = (0.3 < ma_long_chg_norm and ma_long_chg_norm <= 0.7 and close > topmid2) and not (adx_chg > adx_chg[1]) // and adx_match_thresh and not (ma_long_chg_norm_chg > 0.1)
ma_long_chg_norm_pos_sell2 = (0.7 < ma_long_chg_norm and ma_long_chg_norm <= 1 and close > topmid3) and not (adx_chg > adx_chg[1]) // and adx_match_thresh and not (ma_long_chg_norm_chg > 0.1)
ma_long_chg_norm_pos_sell3 = (1 < ma_long_chg_norm and ma_long_chg_norm <= 1.5 and close > topmid3) and not (adx_chg > adx_chg[1]) // and adx_match_thresh and not (ma_long_chg_norm_chg > 0.1)
ma_long_chg_norm_pos_sell4 = (1.5 < ma_long_chg_norm and ma_long_chg_norm <= 3 and (close > top3 or rsi >= 85)) and not (adx_chg > adx_chg[1]) // and adx_match_thresh and not (ma_long_chg_norm_chg > 0.1)

ma_long_chg_norm_pos_buy_close1 = (0 < ma_long_chg_norm and ma_long_chg_norm <= 0.5 and high > topmid1)
ma_long_chg_norm_pos_buy_close2 = (0.5 < ma_long_chg_norm and ma_long_chg_norm <= 1 and high > top1)
ma_long_chg_norm_pos_buy_close3 = (1 < ma_long_chg_norm and ma_long_chg_norm <= 1.5 and high > top2)
ma_long_chg_norm_pos_buy_close4 = (1.5 < ma_long_chg_norm and ((high > topmid3) or (high > top1 and adx < adx_thresh)))

plot_ma_long_chg_norm_pos_buy = input(true, title="plot_ma_long_chg_norm_pos_buy")
plot_ma_long_chg_norm_pos_buy1 = plot_ma_long_chg_norm_pos_buy ? ma_long_chg_norm_pos_buy1 : na
plotshape(plot_ma_long_chg_norm_pos_buy1, style=shape.labelup, location=location.belowbar, color=orange)
plot_ma_long_chg_norm_pos_buy2 = plot_ma_long_chg_norm_pos_buy ? ma_long_chg_norm_pos_buy2 : na
plotshape(plot_ma_long_chg_norm_pos_buy2, style=shape.labelup, location=location.belowbar, color=teal)
plot_ma_long_chg_norm_pos_buy3 = plot_ma_long_chg_norm_pos_buy ? ma_long_chg_norm_pos_buy3 : na
plotshape(plot_ma_long_chg_norm_pos_buy3, style=shape.labelup, location=location.belowbar, color=fuchsia)
plot_ma_long_chg_norm_pos_buy4 = plot_ma_long_chg_norm_pos_buy ? ma_long_chg_norm_pos_buy4 : na
plotshape(plot_ma_long_chg_norm_pos_buy4, style=shape.labelup, location=location.belowbar, color=lime)
plot_ma_long_chg_norm_pos_buy5 = plot_ma_long_chg_norm_pos_buy ? ma_long_chg_norm_pos_buy5 : na
plotshape(plot_ma_long_chg_norm_pos_buy5, style=shape.labelup, location=location.belowbar, color=navy)

plot_ma_long_chg_norm_pos_sell_close = input(false, title="plot_ma_long_chg_norm_pos_sell_close")
plot_ma_long_chg_norm_pos_sell_close1 = plot_ma_long_chg_norm_pos_sell_close ? ma_long_chg_norm_pos_sell_close1 : na
plotshape(plot_ma_long_chg_norm_pos_sell_close1, style=shape.xcross, location=location.belowbar, color=orange)
plot_ma_long_chg_norm_pos_sell_close2 = plot_ma_long_chg_norm_pos_sell_close ? ma_long_chg_norm_pos_sell_close2 : na
plotshape(plot_ma_long_chg_norm_pos_sell_close2, style=shape.xcross, location=location.belowbar, color=teal)
plot_ma_long_chg_norm_pos_sell_close3 = plot_ma_long_chg_norm_pos_sell_close ? ma_long_chg_norm_pos_sell_close3 : na
plotshape(plot_ma_long_chg_norm_pos_sell_close3, style=shape.xcross, location=location.belowbar, color=fuchsia)
plot_ma_long_chg_norm_pos_sell_close4 = plot_ma_long_chg_norm_pos_sell_close ? ma_long_chg_norm_pos_sell_close4 : na
plotshape(plot_ma_long_chg_norm_pos_sell_close4, style=shape.xcross, location=location.belowbar, color=lime)

plot_ma_long_chg_norm_pos_sell = input(true, title="plot_ma_long_chg_norm_pos_sell")
plot_ma_long_chg_norm_pos_sell1 = plot_ma_long_chg_norm_pos_sell ? ma_long_chg_norm_pos_sell1 : na
plotshape(plot_ma_long_chg_norm_pos_sell1, style=shape.labeldown, location=location.abovebar, color=orange)
plot_ma_long_chg_norm_pos_sell2 = plot_ma_long_chg_norm_pos_sell ? ma_long_chg_norm_pos_sell2 : na
plotshape(plot_ma_long_chg_norm_pos_sell2, style=shape.labeldown, location=location.abovebar, color=teal)
plot_ma_long_chg_norm_pos_sell3 = plot_ma_long_chg_norm_pos_sell ? ma_long_chg_norm_pos_sell3 : na
plotshape(plot_ma_long_chg_norm_pos_sell3, style=shape.labeldown, location=location.abovebar, color=fuchsia)
plot_ma_long_chg_norm_pos_sell4 = plot_ma_long_chg_norm_pos_sell ? ma_long_chg_norm_pos_sell4 : na
plotshape(plot_ma_long_chg_norm_pos_sell4, style=shape.labeldown, location=location.abovebar, color=lime)

plot_ma_long_chg_norm_pos_buy_close = input(false, title="plot_ma_long_chg_norm_pos_buy_close")
plot_ma_long_chg_norm_pos_buy_close1 = plot_ma_long_chg_norm_pos_buy_close ? ma_long_chg_norm_pos_buy_close1 : na
plotshape(plot_ma_long_chg_norm_pos_buy_close1, style=shape.xcross, location=location.abovebar, color=orange)
plot_ma_long_chg_norm_pos_buy_close2 = plot_ma_long_chg_norm_pos_buy_close ? ma_long_chg_norm_pos_buy_close2 : na
plotshape(plot_ma_long_chg_norm_pos_buy_close2, style=shape.xcross, location=location.abovebar, color=teal)
plot_ma_long_chg_norm_pos_buy_close3 = plot_ma_long_chg_norm_pos_buy_close ? ma_long_chg_norm_pos_buy_close3 : na
plotshape(plot_ma_long_chg_norm_pos_buy_close3, style=shape.xcross, location=location.abovebar, color=fuchsia)
plot_ma_long_chg_norm_pos_buy_close4 = plot_ma_long_chg_norm_pos_buy_close ? ma_long_chg_norm_pos_buy_close4 : na
plotshape(plot_ma_long_chg_norm_pos_buy_close4, style=shape.xcross, location=location.abovebar, color=lime)


ma_long_chg_norm_neg_buy1 = (0 > ma_long_chg_norm and ma_long_chg_norm >= -0.5 and close < bot1) and not (adx_chg < adx_chg[1])
ma_long_chg_norm_neg_buy2 = (-0.5 > ma_long_chg_norm and ma_long_chg_norm >= -1 and close < botmid2) and not (adx_chg < adx_chg[1])
ma_long_chg_norm_neg_buy3 = (-1 > ma_long_chg_norm and ma_long_chg_norm >= -1.5 and close < botmid3) and not (adx_chg < adx_chg[1])
ma_long_chg_norm_neg_buy4 = (-1.5 > ma_long_chg_norm and ma_long_chg_norm >= -2 and close < bot3) and not (adx_chg < adx_chg[1])

ma_long_chg_norm_neg_sell_close1 = (0 > ma_long_chg_norm and ma_long_chg_norm >= -0.5 and low < mid)
ma_long_chg_norm_neg_sell_close2 = (-0.5 > ma_long_chg_norm and ma_long_chg_norm >= -1 and low < botmid1)
ma_long_chg_norm_neg_sell_close3 = (-1 > ma_long_chg_norm and ma_long_chg_norm >= -1.5 and low < botmid2)
ma_long_chg_norm_neg_sell_close4 = na // (-1.5 > ma_long_chg_norm and ma_long_chg_norm >= -2 and (low < bot3 or (low < botmid2 and ma_long_chg_norm < ma_long_chg)))

ma_long_chg_norm_neg_sell1 = (0 > ma_long_chg_norm and ma_long_chg_norm >= -0.5 and close > topmid1) and not (adx_chg > adx_chg[1]) // and not adx_up
ma_long_chg_norm_neg_sell2 = (-0.5 > ma_long_chg_norm and ma_long_chg_norm >= -1 and close > mid) and not (adx_chg > adx_chg[1]) // and not adx_up
ma_long_chg_norm_neg_sell3 = (-1 > ma_long_chg_norm and ma_long_chg_norm >= -1.5 and close > botmid1) and not (adx_chg > adx_chg[1]) // and not adx_up
ma_long_chg_norm_neg_sell4 = (-1.5 > ma_long_chg_norm and ma_long_chg_norm >= -2 and close > botmid2) and not (adx_chg > adx_chg[1]) // and not adx_up

ma_long_chg_norm_neg_buy_close1 = (0 > ma_long_chg_norm and ma_long_chg_norm >= -0.5 and high > topmid1)
ma_long_chg_norm_neg_buy_close2 = (-0.5 > ma_long_chg_norm and ma_long_chg_norm >= -1 and high > botmid1)
ma_long_chg_norm_neg_buy_close3 = (-1 > ma_long_chg_norm and ma_long_chg_norm >= -1.5 and high > botmid2)
ma_long_chg_norm_neg_buy_close4 = na // (-1.5 > ma_long_chg_norm and ma_long_chg_norm >= -2 and high > botmid3)


plot_ma_long_chg_norm_neg_buy = input(true, title="plot_ma_long_chg_norm_neg_buy")
plot_ma_long_chg_norm_neg_buy1 = plot_ma_long_chg_norm_neg_buy ? ma_long_chg_norm_neg_buy1 : na
plotshape(plot_ma_long_chg_norm_neg_buy1, style=shape.labelup, location=location.belowbar, color=orange)
plot_ma_long_chg_norm_neg_buy2 = plot_ma_long_chg_norm_neg_buy ? ma_long_chg_norm_neg_buy2 : na
plotshape(plot_ma_long_chg_norm_neg_buy2, style=shape.labelup, location=location.belowbar, color=teal)
plot_ma_long_chg_norm_neg_buy3 = plot_ma_long_chg_norm_neg_buy ? ma_long_chg_norm_neg_buy3 : na
plotshape(plot_ma_long_chg_norm_neg_buy3, style=shape.labelup, location=location.belowbar, color=fuchsia)
plot_ma_long_chg_norm_neg_buy4 = plot_ma_long_chg_norm_neg_buy ? ma_long_chg_norm_neg_buy4 : na
plotshape(plot_ma_long_chg_norm_neg_buy4, style=shape.labelup, location=location.belowbar, color=lime)

plot_ma_long_chg_norm_neg_sell_close = input(false, title="plot_ma_long_chg_norm_neg_sell_close")
plot_ma_long_chg_norm_neg_sell_close1 = plot_ma_long_chg_norm_neg_sell_close ? ma_long_chg_norm_neg_sell_close1 : na
plotshape(plot_ma_long_chg_norm_neg_sell_close1, style=shape.xcross, location=location.belowbar, color=orange)
plot_ma_long_chg_norm_neg_sell_close2 = plot_ma_long_chg_norm_neg_sell_close ? ma_long_chg_norm_neg_sell_close2 : na
plotshape(plot_ma_long_chg_norm_neg_sell_close2, style=shape.xcross, location=location.belowbar, color=teal)
plot_ma_long_chg_norm_neg_sell_close3 = plot_ma_long_chg_norm_neg_sell_close ? ma_long_chg_norm_neg_sell_close3 : na
plotshape(plot_ma_long_chg_norm_neg_sell_close3, style=shape.xcross, location=location.belowbar, color=fuchsia)
plot_ma_long_chg_norm_neg_sell_close4 = plot_ma_long_chg_norm_neg_sell_close ? ma_long_chg_norm_neg_sell_close4 : na
plotshape(plot_ma_long_chg_norm_neg_sell_close4, style=shape.xcross, location=location.belowbar, color=lime)

plot_ma_long_chg_norm_neg_sell = input(true, title="plot_ma_long_chg_norm_neg_sell")
plot_ma_long_chg_norm_neg_sell1 = plot_ma_long_chg_norm_neg_sell ? ma_long_chg_norm_neg_sell1 : na
plotshape(plot_ma_long_chg_norm_neg_sell1, style=shape.labeldown, location=location.abovebar, color=orange)
plot_ma_long_chg_norm_neg_sell2 = plot_ma_long_chg_norm_neg_sell ? ma_long_chg_norm_neg_sell2 : na
plotshape(plot_ma_long_chg_norm_neg_sell2, style=shape.labeldown, location=location.abovebar, color=teal)
plot_ma_long_chg_norm_neg_sell3 = plot_ma_long_chg_norm_neg_sell ? ma_long_chg_norm_neg_sell3 : na
plotshape(plot_ma_long_chg_norm_neg_sell3, style=shape.labeldown, location=location.abovebar, color=fuchsia)
plot_ma_long_chg_norm_neg_sell4 = plot_ma_long_chg_norm_neg_sell ? ma_long_chg_norm_neg_sell4 : na
plotshape(plot_ma_long_chg_norm_neg_sell4, style=shape.labeldown, location=location.abovebar, color=lime)

plot_ma_long_chg_norm_neg_buy_close = input(false, title="plot_ma_long_chg_norm_neg_buy_close")
plot_ma_long_chg_norm_neg_buy_close1 = plot_ma_long_chg_norm_neg_buy_close ? ma_long_chg_norm_neg_buy_close1 : na
plotshape(plot_ma_long_chg_norm_neg_buy_close1, style=shape.xcross, location=location.abovebar, color=orange)
plot_ma_long_chg_norm_neg_buy_close2 = plot_ma_long_chg_norm_neg_buy_close ? ma_long_chg_norm_neg_buy_close2 : na
plotshape(plot_ma_long_chg_norm_neg_buy_close2, style=shape.xcross, location=location.abovebar, color=teal)
plot_ma_long_chg_norm_neg_buy_close3 = plot_ma_long_chg_norm_neg_buy_close ? ma_long_chg_norm_neg_buy_close3 : na
plotshape(plot_ma_long_chg_norm_neg_buy_close3, style=shape.xcross, location=location.abovebar, color=fuchsia)
plot_ma_long_chg_norm_neg_buy_close4 = plot_ma_long_chg_norm_neg_buy_close ? ma_long_chg_norm_neg_buy_close4 : na
plotshape(plot_ma_long_chg_norm_neg_buy_close4, style=shape.xcross, location=location.abovebar, color=lime)

kama_buy = 0 > ma_long_chg_norm and ma_long_chg_norm > -1 and 0 < kama_chg_avg and kama_chg_avg < kama_chg_avg_thresh and not (kama_chg < -0.1) and close < mid
kama_sell = 0 < ma_long_chg_norm and ma_long_chg_norm < 1 and 0 > kama_chg_avg and kama_chg_avg > -kama_chg_avg_thresh and not (kama_chg > 0.1) and close > mid

plot_kama = input(true, title="plot_kama")
plot_kama_buy = plot_kama ? kama_buy : na
plotshape(plot_kama_buy, style=shape.diamond, location=location.belowbar, color=purple)
plot_kama_sell = plot_kama ? kama_sell : na
plotshape(plot_kama_sell, style=shape.diamond, location=location.abovebar, color=purple)

buy_sig = na
sell_sig = na
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

// Plot indicator signal
// plot_ind = input(false, title="plot_ind")
// plot_ind := plot_ind ? ind : na
// plotshape(plot_ind, style=shape.circle, location=location.belowbar, color=purple)
