from pprint import pprint
from datetime import datetime, timezone, timedelta
import ccxt.async as ccxt
import calendar
import inspect
import logging
import json
import pandas as pd

logger = logging.getLogger()

INF = 9999999

def load_config():
    with open('../settings/config.json') as f:
        return json.load(f)


config = load_config()
consts = config['constants']
currencies = config['currencies']


def get_keys():
    with open('../settings/keys.json') as f:
        return json.load(f)


def combine(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        return {**a, **b}
    elif isinstance(a, list) and isinstance(b, list):
        return a + b


def ms_dt(ms):
    """ Convert timestamp in millisecond to datetime. """
    return datetime.fromtimestamp(int(float(ms)/1000))


def utcms_dt(ms):
    return datetime.utcfromtimestamp(int(float(ms)/1000))


def dt_ms(year, month, day, hour=0, min=0, sec=0):
    """ Covert datetime to milliscond. """
    return int(datetime(year, month, day, hour, min, sec).timestamp()*1000)


def ms_sec(ms):
    return int(float(ms)/1000)


def sec_ms(sec):
    return int(float(sec)*1000)


def datetime_str(year, month, day, hour=0, min=0, sec=0):
    dt = datetime(year, month, day, hour, min, sec)
    return dt.strftime('%Y-%m-%d %H:%M:%S')


def to_utc_timestamp(timestamp):
    """ Convert local timestamp to utc. """
    tdelta = datetime.now().timestamp() - datetime.utcnow().timestamp()
    return timestamp - sec_ms(tdelta.timestamp())


def to_local_timestamp(timestamp):
    """ Convert local timestamp to utc. """
    tdelta = datetime.now().timestamp() - datetime.utcnow().timestamp()
    return timestamp + sec_ms(tdelta.timestamp())


def exchange_timestamp(year, month, day, hour=0, min=0, sec=0):
    dt = datetime(year, month, day, hour, min, sec)
    return calendar.timegm(dt.utctimetuple()) * 1000


def timeframe_timedelta(timeframe):
    if 'M' == timeframe[-1]:
        period = int(timeframe.split('M')[0])
        return timedelta(months=period)
    elif 'D' == timeframe[-1]:
        period = int(timeframe.split('D')[0])
        return timedelta(days=period)
    elif 'h' == timeframe[-1]:
        period = int(timeframe.split('h')[0])
        return timedelta(hours=period)
    elif 'm' == timeframe[-1]:
        period = int(timeframe.split('m')[0])
        return timedelta(minutes=period)
    else:
        raise ValueError(f'Invalid timeframe \'{timeframe}\'')


def init_ccxt_exchange(exchange_id):
    """ Return an initialized ccxt API instance. """
    options = combine({
        'rateLimit': consts['rate_limit'],
        'enableRateLimit': True
    }, get_keys()[exchange_id])

    exchange = getattr(ccxt, exchange_id)(options)
    return exchange


def not_implemented():
    filename = inspect.stack()[1][1]
    funcname = inspect.stack()[1][3]
    raise NotImplementedError(f'{filename} >> `{funcname}` is not implemented.')


def ld_to_dl(ld):
    """ Convert a list of dicts to a dict of lists
        e.g.
            [{'A':1, 'B':2, 'C':3},
             {'A':4, 'B':5, 'C':6}]
        to
            {'A': [1, 4],
             'B': [2, 5],
             'C': [3, 6] }
    """
    out = {}
    keys = ld[0].keys()
    for k in keys:
        l = []
        for i in range(len(ld)):
            l += [ld[i][k]]
        out[k] = l
    return out


def timeframe_to_freq(timeframe):
    freq = ''
    if timeframe[-1] == 'm':
        freq = timeframe[:-1]+'T' # min
    elif timeframe[-1] == 'h':
        freq = timeframe[:-1]+'H'
    elif timeframe[-1] == 'd':
        freq = timeframe[:-1]+'D'
    elif timeframe[-1] == 'M':
        freq = timeframe[:-1]+'M'
    else:
        raise ValueError(f"Cannot interpret timeframe "\
                         f"{timeframe} to pandas frequency.")
    return freq


class EXPeriod():

    def __init__(self, timeframe):
        self.freq = timeframe_to_freq(timeframe)

    def utcms_period(self, ms):
        return pd.Period(datetime.utcfromtimestamp(int(float(ms)/1000)), self.freq)

    def datetime_period(self, dt):
        return pd.Period(dt, self.freq)


def dataframe_diff(df1, df2):
    merged = df1.merge(df2, indicator=True, how='outer')
    diff_l = merged[merged['_merge'] == 'left_only']
    diff_r = merged[merged['_merge'] == 'right_only']
    return pd.concat([diff_l, diff_r], copy=False)


def exchange_name(ex):
    if not isinstance(ex, str):
        ex = 'bitfinex' if ex.id == 'bitfinex2' else ex.id
    return ex

