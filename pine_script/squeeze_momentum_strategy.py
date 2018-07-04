//@version=3
strategy("Squeeze Momentum", pyramiding=0, overlay=false, default_qty_type=strategy.percent_of_equity, default_qty_value=90, commission_type=strategy.commission.percent, commission_value=0.3)

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

bb_len = input(20, title="BB Length")
kc_len = input(20, title="KC Length")
kc_mult = input(1.5, title="KC MultFactor")

useTrueRange = input(true, title="Use TrueRange (KC)", type=bool)

// Calculate BB
source = close
basis = sma(source, bb_len)
dev = kc_mult * stdev(source, bb_len)
upperBB = basis + dev
lowerBB = basis - dev

// Calculate KC
ma = sma(source, kc_len)
range = useTrueRange ? tr : (high - low)
rangema = sma(range, kc_len)
upperKC = ma + rangema * kc_mult
lowerKC = ma - rangema * kc_mult

sqzOn  = (lowerBB > lowerKC) and (upperBB < upperKC)
sqzOff = (lowerBB < lowerKC) and (upperBB > upperKC)
noSqz  = (sqzOn == false) and (sqzOff == false)

val = linreg(source - avg(avg(highest(high, kc_len), lowest(low, kc_len)),sma(close,kc_len)), kc_len,0)

sqz_buy = val > val[1]
sqz_sell = val < val[1]

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
bcolor = val > 0 ? (val > val[1] ? lime : green) : (val < val[1] ? red : maroon)
scolor = noSqz ? blue : sqzOn ? black : gray
plot(val, color=bcolor, style=histogram, linewidth=4)
plot(0, color=scolor, style=cross, linewidth=2)

///////////////////////////////////////////////////////////////////////////////