from datetime import datetime

import logging
import pandas as pd

from utils import \
    sec_ms, \
    ms_sec,\
    tf_td,\
    ms_dt,\
    dt_ms,\
    MIN_DT, \
    MAX_DT, \
    timeframe_to_freq,\
    handle_ccxt_request, \
    ohlcv_to_interval, \
    true_symbol

from db import EXMongo

logger = logging.getLogger('pyct')


async def fetch_ohlcv(ex, symbol, start, end, timeframe='1m', log=True):
    """ Fetch all ohlcv ohlcv since 'start_timestamp' and use generator to stream results. """
    if start >= end:
        raise ValueError(f"start {start} should < end {end}.")

    start = dt_ms(start)
    end = dt_ms(end)

    params = {'end': end, 'limit': 1000, 'sort': 1}

    await ex.load_markets()
    symbol = true_symbol(ex, symbol)

    while start < end:
        if log:
            logger.info(
                f'Fetching {symbol} {timeframe} ohlcv from {ms_dt(start)} to {ms_dt(end)}'
            )

        ohlcv = await handle_ccxt_request(
            ex.fetch_ohlcv,
            symbol,
            timeframe=timeframe,
            since=start,
            params=params)

        if not ohlcv or ohlcv[-1][0] == start:  # no ohlcv in the period
            start = end
        else:
            start = ohlcv[-1][0] + 1000 # + 1 sec

        yield ohlcv


async def fetch_trades(ex, symbol, start, end, log=True):
    def remove_last_timestamp(records):
        _last_timestamp = records[-1]['timestamp']
        ts = ms_sec(_last_timestamp)

        i = -1
        last_idx = -1
        for n in range(0, len(records) - 1):
            if ms_sec(records[i-n]['timestamp']) == ts:
                last_idx = i - n
            else:
                break

        return _last_timestamp, records[:last_idx]

    start = dt_ms(start)
    end = dt_ms(end)

    params = {'start': start, 'end': end, 'limit': 200, 'sort': 1}

    await ex.load_markets()
    symbol = true_symbol(ex, symbol)

    while start < end:
        if log:
            logger.info(
                f'Fetching {symbol} trades starting from {ms_dt(start)}')

        trades = await handle_ccxt_request(
            ex.fetch_trades, symbol, params=params)

        if len(trades) is 0:
            break

        if trades[0]['timestamp'] == trades[-1]['timestamp']:
            # All 120 trades have the same timestamp,
            # (120 transactions in 1 sec, which is unlikely to happen)
            # just ignore the rest of trades that have same timestamp,
            # no much we can do about it.
            start += 1000

        if not trades or trades[-1]['timestamp'] == end:
            start = trades[-1]['timestamp'] + 1000
        else:
            start, trades = remove_last_timestamp(trades)

        params['start'] = start

        yield trades


async def fetch_my_trades(ex,
                          symbol,
                          start,
                          end=None,
                          parser=None,
                          log=True):
    """ Fetch all trades in a period. """
    if end and start >= end:
        raise ValueError(f"start {start} should < end {end}.")

    start = dt_ms(start)
    end = dt_ms(end) if end else None
    limit = 1000

    params = {}
    params['reverse'] = 1
    if end:
        params['until'] = end

    while True:
        if log:
            logger.info(
                f'Fetching account trades starting from {ms_dt(start)}')

        res = await handle_ccxt_request(ex.fetch_my_trades, symbol,
                                        start, limit, params)
        trades = []

        for trade in res:
            if parser:
                trade = parser(trade)
            else:
                trade.pop('info', None)
            trades.append(trade)

        if len(trades) is 0:
            break
        else:
            start = trades[-1]['timestamp'] + 1  # +1 ms because many trades may occur within 1 sec

        yield trades


def is_empty_response(err):
    return True if str(err).find('empty response') >= 0 else False


async def find_missing_ohlcv(coll, start, end, timeframe):

    start = dt_ms(start)
    end = dt_ms(end)

    if not await EXMongo.check_columns(
            coll, ['timestamp', 'open', 'close', 'high', 'low', 'volume']):
        raise ValueError('Collection\'s fields do not match candle\'s.')

    td = tf_td(timeframe)
    td = sec_ms(td.seconds)

    prev_ts = start - td
    ts = None

    res = coll.find({
        'timestamp': {
            '$gte': start,
            '$lt': end
        }
    }).sort('timestamp', 1)

    missing_ohlcv = []
    async for ohlcv in res:
        ts = ohlcv['timestamp']
        while prev_ts + td <= ts:
            if prev_ts + td != ts:
                missing_ohlcv.append(prev_ts + td)
            prev_ts += td

    ts = end - 1
    while prev_ts + td <= ts:
        if prev_ts + td != ts:
            missing_ohlcv.append(prev_ts + td)
        prev_ts += td

    return missing_ohlcv


async def fill_missing_ohlcv(mongo, ex, symbol, start, end, timeframe):
    def fill_ohlcv(df):
        for i in range(len(df)):
            row = df.iloc[i]
            if pd.isna(row.close):
                if i == 0:
                    raise ValueError("Starting ohlcv is empty.")

                c = df.iloc[i - 1].close
                row.open = row.close = c
                row.high = row.low = c
                row.volume = 0

    df = await mongo.get_ohlcv(ex, symbol, timeframe, start, end)
    df = df.asfreq(timeframe_to_freq(timeframe))

    fill_ohlcv(df)
    return df


async def build_ohlcv(mongo, ex, symbol, src_tf, target_tf, *,
                      start=None, end=None, coll_prefix='', upsert=True):
    start = start or MIN_DT
    end = end or MAX_DT

    src_df = await mongo.get_ohlcv(ex, symbol, src_tf, start, end)
    target_td = tf_td(target_tf)
    target_df = ohlcv_to_interval(src_df, src_tf, target_td)

    await mongo.insert_ohlcv(
        target_df, ex, symbol, target_tf, coll_prefix=coll_prefix, upsert=upsert)


async def compare_ohlcvs(mongo, ex, symbol, tf, prefix_1, prefix_2):
    start = MIN_DT
    end = MAX_DT

    ohlcv_1 = await mongo.get_ohlcv(
        ex, symbol, tf, start, end, coll_prefix=prefix_1)

    ohlcv_2 = await mongo.get_ohlcv(
        ex, symbol, tf, start, end, coll_prefix=prefix_2)

    start = max(ohlcv_1.index[0], ohlcv_2.index[0])
    end = min(ohlcv_1.index[-1], ohlcv_2.index[-1])
    diff = ohlcv_1[start:end] == ohlcv_2[start:end]

    return diff
