from datetime import datetime

import logging
import time
import pandas as pd

from utils import \
    sec_ms, \
    ms_sec,\
    tf_td,\
    ms_dt,\
    dt_ms,\
    MIN_DT, \
    timeframe_to_freq,\
    config, \
    handle_ccxt_request, \
    ohlcv_to_interval

from db import EXMongo

logger = logging.getLogger('pyct')


async def fetch_ohlcv(exchange, symbol, start, end, timeframe='1m', log=True):
    """ Fetch all ohlcv ohlcv since 'start_timestamp' and use generator to stream results. """
    if start >= end:
        raise ValueError(f"start {start} should < end {end}.")

    start = dt_ms(start)
    end = dt_ms(end)

    params = {'end': end, 'limit': 1000, 'sort': 1}

    while start < end:
        if log:
            logger.info(
                f'Fetching {symbol} {timeframe} ohlcv from {ms_dt(start)} to {ms_dt(end)}'
            )

        ohlcv = await handle_ccxt_request(
            exchange.fetch_ohlcv,
            symbol,
            timeframe=timeframe,
            since=start,
            params=params)

        if len(ohlcv) is 0 or ohlcv[-1][0] == start:  # no ohlcv in the period
            start = end
        else:
            start = ohlcv[-1][0] + 1000

        yield ohlcv


async def fetch_trades(exchange, symbol, start, end, log=True):
    def remove_last_timestamp(records):
        _last_timestamp = records[-1]['timestamp']
        ts = ms_sec(_last_timestamp)

        i = -1
        for _ in range(1, len(records) - 1):
            if ms_sec(records[i]['timestamp']) == ts:
                del records[i]
            else:
                break

        return _last_timestamp, records

    start = dt_ms(start)
    end = dt_ms(end)

    params = {'start': start, 'end': end, 'limit': 1000, 'sort': 1}

    while start < end:
        if log:
            logger.info(
                f'Fetching {symbol} trades starting from {ms_dt(start)}')

        trades = await handle_ccxt_request(
            exchange.fetch_trades, symbol, params=params)

        if len(trades) is 0:
            break

        if trades[0]['timestamp'] == trades[-1]['timestamp']:
            # All 1000 trades have the same timestamp,
            # (1000 transactions in 1 sec, which is unlikely to happen)
            # just ignore the rest of trades that have same timestamp,
            # no much we can do about it.
            start += 1000

        if len(trades) < params['limit']:
            start = trades[-1]['timestamp'] + 1000
        else:
            start, trades = remove_last_timestamp(trades)

        params['start'] = start

        yield trades


async def fetch_my_trades(exchange,
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

        res = await handle_ccxt_request(exchange.fetch_my_trades, symbol,
                                        start, limit, params)
        trades = []

        for trade in res:
            if parser:
                trade = parser(trade)
            else:
                del trade['info']
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


async def fill_missing_ohlcv(mongo, exchange, symbol, start, end, timeframe):
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

    df = await mongo.get_ohlcv(exchange, symbol, timeframe, start, end)
    df = df.asfreq(timeframe_to_freq(timeframe))

    fill_ohlcv(df)
    return df


async def build_ohlcv(mongo, exchange, symbol, src_tf, target_tf, *,
                      start=None, end=None, coll_prefix='', upsert=True):
    start = MIN_DT if not start else start
    end = datetime(9999, 1, 1) if not end else end

    src_df = await mongo.get_ohlcv(exchange, symbol, src_tf, start, end)
    target_td = tf_td(target_tf)
    target_df = ohlcv_to_interval(src_df, src_tf, target_td)

    await mongo.insert_ohlcv(
        target_df, exchange, symbol, target_tf, coll_prefix=coll_prefix, upsert=upsert)
