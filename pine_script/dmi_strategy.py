//@version=2
strategy("DMI Strategy", pyramiding=0, default_qty_type=strategy.percent_of_equity, default_qty_value=90, commission_type=strategy.commission.percent, commission_value=0.3)

//////////////////////////////////////////////////////////////////////
// Component Code Start
testStartYear = input(2017, "Backtest Start Year")
testStartMonth = input(8, "Backtest Start Month")
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

ADX(dilen, adxlen) =>
    up = change(high)
    down = -change(low)
    truerange = ema(tr, dilen)
    pdi = fixnan(100 * ema(up > down and up > 0 ? up : 0, dilen) / truerange)
    mdi = fixnan(100 * ema(down > up and down > 0 ? down : 0, dilen) / truerange)
    adx = 100 * ema(abs(pdi - mdi) / ((pdi + mdi) == 0 ? 1 : (pdi + mdi)), adxlen)
    [adx, pdi, mdi]

NORM_MOM(src, momlen, malen, malen2) =>
    mom = mom(src, momlen)
    norm_mom = mom / src * 100

STOCHRSI(src, rsilen, stochlen, klen, dlen) =>
    rsi = rsi(src, rsilen)
    k = sma(stoch(rsi, rsi, rsi, stochlen), klen)
    d = sma(k, dlen)
    [k, d]

stop_loss = input(2000, step=500, title="Stop Loss")
trail_stop = input(1000, step=500, title="Profit Trailing Stop")
trail_offset = input(19000, step=500, title="Profit Trailing Stop Offset")

adxlen = input(40, title="ADX Length")
dilen = input(12, title="DI Length")

base_thresh = input(20, title="Base Threshold")
adx_thresh = input(25, title="ADX Threshold")
di_top_thresh = input(30, title="DI Top Threshold")
di_bot_thresh = input(15, title="DI bot Threshold")

adx_top_peak_diff = input(1, step=0.1, title="ADX Top Peak Diff")
adx_bot_peak_diff = input(1, step=0.1, title="ADX Bottom Peak Diff")
di_diff = input(13, title="DI Diff")

ema_length = input(9, title="EMA Length")
rsi_length = input(14, title="RSI Length")
rsi_mom_thresh = input(25, title="RSI Momentum Threshold")

stoch_rsi_length = input(14, title="Stoch RSI Length")
stoch_length = input(10, title="Stoch Length")
k_length = input(3, title="Stoch K Length")
d_length = input(3, title="Stoch D Length")
stochrsi_upper = input(80, title="StochRSI Upper Threshold")
stochrsi_lower = input(20, title="StochRSI Lower Threshold")

mom_length = input(20, title="Momentum Length")
mom_ma_length = input(10, title="Momentum MA Length")
mom_ma2_length = input(10, title="Momentum Second MA Length")
mom_mid_zone_range = input(7, title="Momentum Mid Zone Range")

[adx, pdi, mdi] = ADX(dilen, adxlen)
ema = ema(close, ema_length)
rsi = rsi(close, rsi_length)
mom = NORM_MOM(close, mom_length, mom_ma_length, mom_ma2_length)
[k, d] = STOCHRSI(close, stoch_rsi_length, stoch_length, k_length, d_length)

mom_mid_zone = (mom < mom_mid_zone_range) and (mom > -mom_mid_zone_range)

top_peak = (adx < adx[1]) and (adx[1] > adx[2]) ? adx[1] : top_peak[1]
bot_peak = (adx > adx[1]) and (adx[1] < adx[2]) ? adx[1] : bot_peak[1]

top_peak_trend = (adx < adx[1]) and (adx[1] > adx[2]) ? (pdi[1] > mdi[1]) ? 1 : -1 : top_peak_trend[1]
bot_peak_trend = (adx > adx[1]) and (adx[1] < adx[2]) ? (pdi[1] > mdi[1]) ? 1 : -1 : bot_peak_trend[1]

top_peak_diff = top_peak - adx_top_peak_diff
bot_peak_diff = bot_peak + adx_bot_peak_diff

// adx_reverse = (adx <= top_peak_diff) and (adx > adx_thresh + 5) and not mom_mid_zone
// adx_rebound = (adx >= bot_peak_diff) and (adx < adx_thresh + 10) and not mom_mid_zone

adx_reverse = (adx <= top_peak_diff) and (adx[1] > top_peak_diff) and (adx > adx_thresh + 5) // and not mom_mid_zone
// adx_rebound = (adx >= bot_peak_diff) and (adx < adx_thresh + 10)
adx_rebound = (adx >= bot_peak_diff) and (adx < adx_thresh + 10)
// adx_rebound := adx_rebound ? adx_rebound : adx_rebound[1] ? adx_rebound[2] ? adx_rebound : adx_rebound[1] : adx_rebound

match_base_thresh = adx >= base_thresh
match_adx_thresh = adx >= adx_thresh
match_di_top_thresh = (pdi >= di_top_thresh) or (mdi >= di_top_thresh)
match_di_diff = abs(pdi - mdi) >= di_diff
cross_base_thresh = (adx[1] < base_thresh) and (adx >= base_thresh)

below_base = (adx[1] >= base_thresh) and not match_base_thresh
no_trend = not match_adx_thresh and not match_di_top_thresh

buy  = (pdi > mdi) and (adx_rebound or cross_base_thresh) and match_base_thresh and not no_trend
sell = (pdi < mdi) and (adx_rebound or cross_base_thresh) and match_base_thresh and not no_trend

buy_reverse = (top_peak_trend == -1) and (pdi > di_bot_thresh) and adx_reverse and match_adx_thresh and match_base_thresh and not no_trend
sell_reverse = (top_peak_trend == 1) and (mdi > di_bot_thresh) and adx_reverse and match_adx_thresh and match_base_thresh and not no_trend

buy_di_turn  = (pdi > mdi) and (pdi[1] < mdi[1]) and (pdi > di_top_thresh) and match_base_thresh and not no_trend
sell_di_turn = (pdi < mdi) and (pdi[1] > mdi[1]) and (mdi > di_top_thresh) and match_base_thresh and not no_trend

ema_up = ema > ema[1]
ema_down = ema < ema[1]

rsi_buy = ((rsi <= 25) and (mom <= -rsi_mom_thresh)) and not (mdi > adx)//or (rsi <= 10)
rsi_sell = ((rsi >= 80) and (mom >= rsi_mom_thresh)) and not (pdi > adx)//or (rsi >= 90)

buy_sig = ((((buy == true) or (buy_reverse == true) or (buy_di_turn == true)) and ema_up) or (rsi_buy)) //and not (rsi > 70)
sell_sig = ((((sell == true) or (sell_reverse == true) or (sell_di_turn == true)) and ema_down) or (rsi_sell)) //and not (rsi <= 30)
close_sig = (below_base == true) or (no_trend == true) //or (((k > 90) and (rsi > 70) and (k < k[1])) or ((k < 10) and (rsi < 30) and (k > k[1])))

// if (buy and testPeriod())
//     strategy.entry("buy", strategy.long)
// if (buy_reverse and testPeriod())
//     strategy.entry("buy_reverse", strategy.long)
// if (buy_di_turn and testPeriod())
//     strategy.entry("buy_turn", strategy.long)

// if (sell and testPeriod())
//     strategy.entry("sell", strategy.short)
// if (sell_reverse and testPeriod())
//     strategy.entry("sell_reverse", strategy.short)
// if (sell_di_turn and testPeriod())
//     strategy.entry("sell_turn", strategy.short)

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

// if (testPeriod())
//     strategy.exit("exit", "buy", trail_points=trail_stop, trail_offset=trail_offset)
//     strategy.exit("exit", "sell", trail_points=trail_stop, trail_offset=trail_offset)

// Plot lines
plot(adx, color=green, linewidth = 3, title="ADX")
plot(pdi, color=blue, linewidth = 2, title="+DI")
plot(mdi, color=red, linewidth = 1, title="-DI")
hline(adx_thresh, color=green, linewidth = 1, title="ADX Thresh")
hline(di_top_thresh, color=purple, linewidth = 1, title="DI Thresh")
hline(base_thresh, color=black, linewidth = 1, title="Base Thresh")

// Plot StochRSI
// plot(k, color=black, linewidth = 1, title="StochRSI K")
// plot(d, color=red, linewidth = 1, title="StochRSI K")
// hline(stochrsi_upper, color=fuchsia, linewidth = 1, title="StochRSI K")
// hline(stochrsi_lower, color=fuchsia, linewidth = 1, title="StochRSI D")

plot(adx_rebound)
plot(buy ? 4 : 3)
