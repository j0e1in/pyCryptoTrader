//@version=3
strategy("KAMA Strategy", pyramiding=0, overlay=true, default_qty_type=strategy.percent_of_equity, default_qty_value=90, commission_type=strategy.commission.percent, commission_value=0.5)

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

kama_len = input(21, minval=1, title="KAMA Length")
kama_chg_avg_len = input(24, minval=1, title="KAMA Chg Avg Length")
kama_chg_open_thresh = input(0.3, step=0.1, title="KAMA Chg Open Threshold")
kama_chg_close_thresh = input(0.3, step=0.1, title="KAMA Chg Close Threshold")
kama_chg_avg_thresh = input(0.1, step=0.1, title="KAMA Chg Avg Threshold")

chg_scale = input(defval=1, step=0.1, title="Chg Scale")

//////////////////////////////////////////////////////////////////////

src = close

kama = KAMA(src, kama_len)

kama_chg = (kama - kama[1]) / kama[1] * 100
kama_chg_avg = sum(kama_chg, kama_chg_avg_len) / kama_chg_avg_len
kama_chg_add_avg = kama_chg + kama_chg_avg

plot(kama, color=blue, linewidth=1, title="KAMA")
plot(kama_chg * chg_scale, color=gray, linewidth=2, title="KAMA Chg")
plot(kama_chg_avg * chg_scale, color=black, linewidth=1, title="KAMA Chg Avg")
plot((kama_chg + kama_chg_avg) * chg_scale, color=orange, linewidth=2, title="KAMA Chg Avg")

//////////////////////////////////////////////////////////////////////

kama_buy = kama_chg_add_avg > kama_chg_open_thresh
kama_sell = kama_chg_add_avg < -kama_chg_open_thresh
kama_close = (kama_chg_add_avg[1] > kama_chg_open_thresh and kama_chg_add_avg < kama_chg_close_thresh)
          or (kama_chg_add_avg[1] < -kama_chg_open_thresh and kama_chg_add_avg > -kama_chg_close_thresh)

buy_sig = kama_buy
sell_sig = kama_sell
close_sig = kama_close

//////////////////////////////////////////////////////////////////////

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