//@version=2
strategy("MOM Strategy", pyramiding=0, default_qty_type=strategy.percent_of_equity, default_qty_value=90, commission_type=strategy.commission.percent, commission_value=0.3)

//////////////////////////////////////////////////////////////////////
// Component Code Start
testStartYear = input(2017, "Backtest Start Year")
testStartMonth = input(11, "Backtest Start Month")
testStartDay = input(1, "Backtest Start Day")
testPeriodStart = timestamp(testStartYear,testStartMonth,testStartDay,0,0)

testStopYear = input(2018, "Backtest Stop Year")
testStopMonth = input(2, "Backtest Stop Month")
testStopDay = input(31, "Backtest Stop Day")
testPeriodStop = timestamp(testStopYear,testStopMonth,testStopDay,0,0)

// A switch to control background coloring of the test period89-=
testPeriodBackgroundColor = (time >= testPeriodStart) and (time <= testPeriodStop) ? #00FF00 : na
bgcolor(testPeriodBackgroundColor, transp=97)

testPeriod() =>
    time >= testPeriodStart and time <= testPeriodStop ? true : false
// Component Code Stop
//////////////////////////////////////////////////////////////////////


stop_loss = input(2000, step=500, title="Stop Loss")
trail_stop = input(1000, step=500, title="Profit Trailing Stop")
trail_offset = input(9000, step=500, title="Profit Trailing Stop Offset")

ema_length = input(9, title="EMA Length")
mom_length = input(20, title="Momentum Length")
mom_ma_length = input(10, title="Momentum MA Length")
mom_ma2_length = input(10, title="Momentum Second MA Length")
mom_mid_zone_range = input(0.1, step=0.01, title="Momentum Mid Zone Range")
mom_norm_mid_zone_range = input(7, title="Normalized Momentum Mid Zone Range")
mom_turn_diff = input(30, title="Momentum Turn Diff")
mom_norm_turn_diff = input(1, step=0.1, title="Normalized Momentum Turn Diff")
norm = input(type=bool, defval=false, title="Normalize Momentum")

NORM_MOM(src) =>
    mom = mom(src, mom_length)
    ma_mom = wma(mom, mom_ma_length)
    ma_mom := ema(ma_mom, mom_ma2_length)
    norm_mom = ma_mom / src * 100

ema = ema(close, ema_length)

mom = if norm
    NORM_MOM(close)
else
    wma(mom(close, mom_length), mom_ma_length)

mom := ema(mom, mom_ma2_length)

ema_up = ema > ema[1]
ema_down = ema < ema[1]

mom_mid_zone = if norm
    (mom < mom_norm_mid_zone_range) and (mom > -mom_norm_mid_zone_range)
else
    mom_mid_zone_range := (mom_mid_zone_range * (highest(close, 90) - lowest(close, 90)))
    (mom < mom_mid_zone_range) and (mom > -mom_mid_zone_range)

turn_diff = if norm
    mom_norm_turn_diff
else
    mom_turn_diff

mom_buy = (mom > mom[1])
mom_sell = (mom < mom[1])
// mom_close = mom_mid_zone and (mom > mom[1] and mom[1] < mom[2] and (mom[2]-mom[1] > turn_diff)) or (mom < mom[1] and mom[1] > mom[2] and (mom[1]-mom[2] > turn_diff))
mom_close = false

buy_sig = mom_buy
sell_sig = mom_sell
close_sig = mom_close

// strategy.close("buy", when=close_sig)
// strategy.close("sell", when=close_sig)
// strategy.close("buy_reverse", when=close_sig)
// strategy.close("sell_reverse", when=close_sig)
// strategy.close("buy_turn", when=close_sig)
// strategy.close("sell_turn", when=close_sig)

// strategy.exit("exit_loss", "buy", loss=stop_loss)
// strategy.exit("exit_loss", "sell", loss=stop_loss)
// strategy.exit("exit_loss", "buy_reverse", loss=stop_loss)
// strategy.exit("exit_loss", "sell_reverse", loss=stop_loss)
// strategy.exit("exit_loss", "buy_turn", loss=stop_loss)
// strategy.exit("exit_loss", "sell_turn", loss=stop_loss)

// strategy.exit("exit_trail", "buy", trail_points=trail_stop, trail_offset=trail_offset)
// strategy.exit("exit_trail", "sell", trail_points=trail_stop, trail_offset=trail_offset)
// strategy.exit("exit_trail", "buy_reverse", trail_points=trail_stop, trail_offset=trail_offset)
// strategy.exit("exit_trail", "sell_reverse", trail_points=trail_stop, trail_offset=trail_offset)
// strategy.exit("exit_trail", "buy_turn", trail_points=trail_stop, trail_offset=trail_offset)
// strategy.exit("exit_trail", "sell_turn", trail_points=trail_stop, trail_offset=trail_offset)

// strategy.exit("exit", "buy", loss=stop_loss, trail_points=trail_stop, trail_offset=trail_offset)
// strategy.exit("exit", "sell", loss=stop_loss, trail_points=trail_stop, trail_offset=trail_offset)
// strategy.exit("exit", "buy_reverse", loss=stop_loss, trail_points=trail_stop, trail_offset=trail_offset)
// strategy.exit("exit", "sell_reverse", loss=stop_loss, trail_points=trail_stop, trail_offset=trail_offset)
// strategy.exit("exit", "buy_turn", loss=stop_loss, trail_points=trail_stop, trail_offset=trail_offset)
// strategy.exit("exit", "sell_turn", loss=stop_loss, trail_points=trail_stop, trail_offset=trail_offset)


sig = close_sig ? 0 : buy_sig ? 1 : sell_sig ? -1 : sig[1]

long  = (sig == 1) ? true : false
short = (sig == -1) ? true : false
exit = (sig == 0) ? true : false

if (long and testPeriod())
    strategy.entry("buy", strategy.long)

if (short and testPeriod())
    strategy.entry("sell", strategy.short)

if (exit and testPeriod())
    strategy.close_all(when=close_sig)

// Momentum
plot(mom, color=orange, linewidth=3, title="Momentum")
plot(0, color=black, linewidth=1, title="Momentum Center")
plot(norm ? mom_norm_mid_zone_range : mom_mid_zone_range, color=blue, linewidth=1, title="Momentum Mid Zone Top")
plot(norm ? -mom_norm_mid_zone_range : -mom_mid_zone_range, color=blue, linewidth=1, title="Momentum Mid Zone Bot")