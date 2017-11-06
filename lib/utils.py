from pprint import pprint
from datetime import datetime, timezone, timedelta
import json


def pp(*args):
    pprint(' '.join([str(arg) for arg in args]))


def get_constants():
    with open('../settings/config.json') as f:
        return json.load(f)['constants']


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
    return datetime.fromtimestamp(int(ms/1000))


def dt_ms(year, month, day, hour=0, min=0, sec=0):
    """ Covert datetime to milliscond.
    """
    return int(datetime(year, month, day, hour, min, sec).timestamp()*1000)


def ms_sec(ms):
    return int(ms/1000)


def sec_ms(sec):
    return int(sec*1000)


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
        period = int(timeframe.split('D')[0])
        return timedelta(minutes=period)
    else:
        raise ValueError(f'Invalid timeframe \'{timeframe}\'')
