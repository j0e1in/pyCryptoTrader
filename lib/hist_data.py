import ccxt.async as ccxt
from ccxt.base.exchange import Exchange
from datetime import timedelta
import asyncio
import logging
import time
import pandas as pd

from utils import config, \
                  sec_ms, ms_sec, \
                  timeframe_timedelta, \
                  ms_dt, \
                  timeframe_to_freq, \
                  INF
from db import EXMongo

## TODO: build ohlcvs from trades and check they matches ohlcvs downloaded from exchange

logger = logging.getLogger()


async def fetch_ohlcv(exchange, symbol, start, end, timeframe='1m'):
    """ Fetch all ohlcv ohlcv since 'start_timestamp' and use generator to stream results. """
    now = sec_ms(time.time())
    wait = config['constants']['wait']
    params = {
        'end': end,
        'limit': 1000,
        'sort': 1
    }

    while start < end:
        try:
            logger.info(f'Fetching {symbol}_{timeframe} ohlcv starting from {ms_dt(start)}')
            ohlcvs = await exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=start, params=params)
            start = ohlcvs[-1][0] + 1000
            yield ohlcvs

        except (ccxt.AuthenticationError,
                ccxt.ExchangeNotAvailable,
                ccxt.RequestTimeout,
                ccxt.ExchangeError,
                ccxt.DDoSProtection) as error:

            if is_empty_response(error): # finished fetching all ohlcv
                break
            elif isinstance(error, ccxt.ExchangeError):
                raise error

            logger.info(f'|{type(error).__name__}| retrying in {wait} seconds...')
            await asyncio.sleep(wait)


async def fetch_trades(exchange, symbol, start, end):

    def remove_last_timestamp(records):
        _last_timestamp = records[-1]['timestamp']
        ts = ms_sec(_last_timestamp)

        i = -1
        for _ in range(1, len(records)-1):
            if ms_sec(records[i]['timestamp']) == ts:
                del records[i]
            else:
                break

        return _last_timestamp, records


    now = sec_ms(time.time())
    wait = config['constants']['wait']
    params = {
        'start': start,
        'end': end,
        'limit': 1000,
        'sort': 1
    }

    while start < end:
        try:
            logger.info(f'Fetching {symbol} trades starting from {ms_dt(start)}')
            trades = await exchange.fetch_trades(symbol, params=params)
            if not trades:
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

        except (ccxt.AuthenticationError,
                ccxt.ExchangeNotAvailable,
                ccxt.RequestTimeout,
                ccxt.ExchangeError,
                ccxt.DDoSProtection) as error:

            if is_empty_response(error): # finished fetching all trades
                break
            elif isinstance(error, ccxt.ExchangeError):
                raise error

            logger.info(f'|{type(error).__name__}| retrying in {wait} seconds...')
            await asyncio.sleep(wait)


def is_empty_response(err):
    return True if 'empty response' in str(err) else False


async def find_missing_ohlcv(coll, start, end, timeframe):

    if not await EXMongo.check_columns(coll,
            ['timestamp', 'open', 'close', 'high', 'low', 'volume']):
        raise ValueError('Collection\'s fields do not match candle\'s.')

    td = timeframe_timedelta(timeframe)
    td = sec_ms(td.seconds)

    prev_ts = start - td
    ts = None

    res = coll.find({'timestamp': {'$gte': start, '$lt': end}}).sort('timestamp', 1)

    missing_ohlcv = []
    async for ohlcv in res:
        ts = ohlcv['timestamp']
        while prev_ts+td <= ts:
            if prev_ts+td != ts:
                missing_ohlcv.append(prev_ts+td)
            prev_ts += td

    ts = end - 1
    while prev_ts+td <= ts:
        if prev_ts+td != ts:
            missing_ohlcv.append(prev_ts+td)
        prev_ts += td

    return missing_ohlcv


async def fill_missing_ohlcv(mongo, exchange, symbol, start, end, timeframe):

    def fill_ohlcv(df):
        for i in range(len(df)):
            row = df.iloc[i]
            if pd.isna(row.close):
                if i == 0:
                    raise ValueError("Starting ohlcv is empty.")

                c = df.iloc[i-1].close
                row.open = row.close = c
                row.high = row.low = c
                row.volume = 0

    df = await mongo.get_ohlcv(exchange, symbol, start, end, timeframe)
    df = df.asfreq(timeframe_to_freq(timeframe))

    fill_ohlcv(df)
    return df

