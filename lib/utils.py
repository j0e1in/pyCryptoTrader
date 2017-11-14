from pprint import pprint
from datetime import datetime, timezone, timedelta
import ccxt.async as ccxt
import calendar
import inspect
import logging
import json

logger = logging.getLogger()

INF = 9999999


def get_constants():
    with open('../settings/config.json') as f:
        return json.load(f)['constants']


consts = get_constants()


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


def init_exchange(exchange_id):
    options = combine({
        'rateLimit': consts['rate_limit'],
        'enableRateLimit': True
    }, get_keys()[exchange_id])

    exchange = getattr(ccxt, exchange_id)(options)
    return exchange


def not_implemented():
    filename = inspect.stack()[1][1]
    funcname = inspect.stack()[1][3]
    logger.warn(f'| {filename} | {funcname}() | is not implemented.')


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
