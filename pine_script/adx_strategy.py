//@version=3
strategy("ADX", pyramiding=10, overlay=false, default_qty_type=strategy.percent_of_equity, default_qty_value=90, commission_type=strategy.commission.percent, commission_value=0.3)

ADX(dilen, adxlen) =>
    up = change(high)
    down = -change(low)
    truerange = ema(tr, dilen)
    pdi = fixnan(100 * ema(up > down and up > 0 ? up : 0, dilen) / truerange)
    mdi = fixnan(100 * ema(down > up and down > 0 ? down : 0, dilen) / truerange)
    adx = 100 * ema(abs(pdi - mdi) / ((pdi + mdi) == 0 ? 1 : (pdi + mdi)), adxlen)
    [adx, pdi, mdi]


adxlen = input(20, title="ADX Length")
dilen = input(20, title="DI Length")
adx_thresh = input(20, title="ADX Threshold")
adx_chg_len = input(3, title="ADX Chg Length")

[adx, pdi, mdi] = ADX(dilen, adxlen)

adx_up   = (pdi > mdi and adx > adx[1]) or (mdi > pdi and adx < adx[1])
adx_down = (pdi > mdi and adx < adx[1]) or (mdi > pdi and adx > adx[1])
adx_match_thresh = adx >= adx_thresh
adx_chg = (adx - adx[adx_chg_len]) / adx * 100
plot(adx, color=lime, linewidth=3)
plot(pdi, color=blue, linewidth=2)
plot(mdi, color=red, linewidth=1)
plot(adx_thresh, color=black, linewidth=1)
plot(adx_chg, color=purple, linewidth=2)
hline(0, linestyle=dashed)