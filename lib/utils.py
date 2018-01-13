from pprint import pprint
from collections import OrderedDict
from datetime import datetime, timezone, timedelta
import ccxt.async as ccxt
import calendar
import inspect
import logging
import json
import pandas as pd
import uuid
import math
import os

logger = logging.getLogger()

INF = 9999999

def get_project_root():
    file_dir = os.path.dirname(os.path.abspath(__file__))
    file_dir = os.path.dirname(file_dir)
    return file_dir

def load_config(file):
    with open(file) as f:
        return json.load(f)


# TODO: Add set_config and get_config method to let classes set and get global config
config = load_config('../settings/config.json')


def load_keys(file=None):
    if not file:
        file = config['key_file']

    with open(file) as f:
        return json.load(f)


def combine(a, b):
    """ Combine two dicts. """
    if isinstance(a, dict) and isinstance(b, dict):
        return {**a, **b}


def ms_dt(ms):
    return datetime.utcfromtimestamp(int(float(ms)/1000))


def dt_ms(dt):
    if isinstance(dt, pd.Timestamp):
        dt = dt.to_pydatetime()
    return calendar.timegm(dt.utctimetuple()) * 1000


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


def utc_ts(year, month, day, hour=0, min=0, sec=0):
    dt = datetime(year, month, day, hour, min, sec)
    return calendar.timegm(dt.utctimetuple()) * 1000


def utc_now():
    """ Return current utc datetime. """
    tdelta = datetime.now() - datetime.utcnow()
    return datetime.now() - tdelta


def timeframe_timedelta(timeframe):
    """ Convert timeframe to timedelta. """
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


def init_ccxt_exchange(ex_id, apikey=None, secret=None):
    """ Return an initialized ccxt API instance. """
    options = {
        'enableRateLimit': True,
        'rateLimit': config['ccxt']['rate_limit'],
        'apiKey': apikey,
        'secret': secret,
    }

    ex = getattr(ccxt, ex_id)(options)
    return ex


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
        freq = timeframe[:-1]+'T'  # min
    elif timeframe[-1] == 'h':
        freq = timeframe[:-1]+'H'
    elif timeframe[-1] == 'd':
        freq = timeframe[:-1]+'D'
    elif timeframe[-1] == 'M':
        freq = timeframe[:-1]+'M'
    else:
        raise ValueError(f"Cannot interpret timeframe "
                         f"{timeframe} to pandas frequency.")
    return freq


def dataframe_diff(df1, df2):
    merged = df1.merge(df2, indicator=True, how='outer')
    diff_l = merged[merged['_merge'] == 'left_only']
    diff_r = merged[merged['_merge'] == 'right_only']
    return pd.concat([diff_l, diff_r], copy=False)


def ex_name(ex):
    if not isinstance(ex, str):
        ex = 'bitfinex' if ex.id == 'bitfinex2' else ex.id
    else:
        ex = 'bitfinex' if ex == 'bitfinex2' else ex
    return ex


def gen_id():
    return uuid.uuid4()


def rsym(symbol):
    """ Convert BTC/USD -> BTCUSD """
    return ''.join(symbol.split('/'))


def select_time(df, start, end):
    """ Return rows with timestamp between start and end.
        `df` must use datetime object as index.
    """
    return df.loc[(df.index >= start) & (df.index < end)]


def roundup_dt(dt, day=0, hour=0, min=0, sec=0):
    """ Round up datetime object to specified interval,
        eg. min = 20, 10:03 => 10:20 (roundup_dt(dt, min=20))
        eg. sec = 120, 10:00 => 10:02 (roundup_dt(dt, sec=120))
    """
    if isinstance(dt, pd.Timestamp):
        dt = dt.to_pydatetime()

    td = timedelta(days=day, hours=hour, minutes=min, seconds=sec)

    day = td.days
    hour = int(td.seconds/60/60)
    min = int(td.seconds/60)
    sec = td.seconds

    if day:
        fill = timedelta(days=day - (dt.day % day))
        rest = timedelta(hours=dt.hour,
                         minutes=dt.minute,
                         seconds=dt.second,
                         microseconds=dt.microsecond)
    elif hour:
        fill = timedelta(hours=hour - (dt.hour % hour))
        rest = timedelta(minutes=dt.minute,
                         seconds=dt.second,
                         microseconds=dt.microsecond)
    elif min:
        fill = timedelta(minutes=min - (dt.minute % min))
        rest = timedelta(seconds=dt.second,
                         microseconds=dt.microsecond)
    elif sec:
        fill = timedelta(seconds=sec - (dt.second % sec))
        rest = timedelta(microseconds=dt.microsecond)
    else:
        raise ValueError("Invalid parameters in roundup_dt.")

    return dt + fill - rest


def rounddown_dt(dt, day=0, hour=0, min=0, sec=0):
    """ Round up datetime object to specified interval,
        eg. min = 20, 10:03 => 10:20 (roundup_dt(dt, min=20))
        eg. sec = 120, 10:00 => 10:02 (roundup_dt(dt, sec=120))
    """
    if isinstance(dt, pd.Timestamp):
        dt = dt.to_pydatetime()

    td = timedelta(days=day, hours=hour, minutes=min, seconds=sec)

    day = td.days
    hour = int(td.seconds/60/60)
    min = int(td.seconds/60)
    sec = td.seconds

    if day:
        fill = timedelta(days=(dt.day % day))
        rest = timedelta(hours=dt.hour,
                         minutes=dt.minute,
                         seconds=dt.second,
                         microseconds=dt.microsecond)
    elif hour:
        fill = timedelta(hours=(dt.hour % hour))
        rest = timedelta(minutes=dt.minute,
                         seconds=dt.second,
                         microseconds=dt.microsecond)
    elif min:
        fill = timedelta(minutes=(dt.minute % min))
        rest = timedelta(seconds=dt.second,
                         microseconds=dt.microsecond)
    elif sec:
        fill = timedelta(seconds=(dt.second % sec))
        rest = timedelta(microseconds=dt.microsecond)
    else:
        raise ValueError("Invalid parameters in rounddown_dt.")

    return dt - fill - rest


def dt_max(d1, d2):
    max_dt = None

    if d1 is not None and d2 is not None:
        max_dt = d1 if d1 > d2 else d2

    if max_dt is None:
        max_dt = d1 if d1 is not None else d2

    return max_dt


def pd_mem_usage(pandas_obj):
    if isinstance(pandas_obj, pd.DataFrame):
        usage_b = pandas_obj.memory_usage(deep=True).sum()
    else:  # we assume if not a df it's a series
        usage_b = pandas_obj.memory_usage(deep=True)
    usage_mb = usage_b / 1024 ** 2  # convert bytes to megabytes
    return "{:03.2f} MB".format(usage_mb)


def set_options(d, **options):
    for k, v in options.items():
        if k not in d:
            d[k] = v


def to_ordered_dict(pairs, sort_by=None):
    """ Pairs can be a list of tuples or a dict.
    """
    if not pairs:
        return OrderedDict()

    od = OrderedDict(pairs)

    if sort_by == 'key':
        od = sorted(od.items(), key=lambda x: x[0])
    elif sort_by == 'value':
        od = sorted(od.items(), key=lambda x: x[1])

    return od


def visualize_dict(dct):

    def interate(dct, tmp_d):
        if not isinstance(dct, dict):
            return '...'

        tmp_d = {k: '...' for k in dct.keys()}
        for k, v in dct.items():
            tmp_d[k] = interate(v, tmp_d[k])
        return tmp_d

    tmp_d = '...'
    tmp_d = interate(dct, tmp_d)
    return tmp_d


def format_value(n, digits=5):
    """ Format value to `digits` digits.
        eg. 10.0012345 => 10.001
            0.0012345678 => 0.0012345
            0.00000123456 => 0.0000012345
    """
    try:
        l = math.log10(n)
    except ValueError:
        raise ValueError(f"Invalid value for log: {n}")
    return round(n, digits-math.ceil(l))


def check_periods(periods):
    for p in periods:
        if p[0] >= p[1]:
            return False
    return True


class Timer():

    def __init__(self, start, interval):
        """ Attribute
                start: timestamp
                interval: seconds
                now: timestamp
        """
        if not isinstance(start, datetime):
            start = ms_dt(start)

        if not isinstance(interval, timedelta):
            interval = timedelta(seconds=interval)

        self.start = start
        self.interval = interval
        self.reset()

    def reset(self):
        self._now = self.start

    def tick(self):
        self._now += self.interval

    def now(self):
        return self._now

    def next(self):
        return self._now + self.interval

    def set_now(self, time):
        if not isinstance(time, datetime):
            time = ms_dt(time)
        self._now = time

    def tsnow(self):
        """ Returns current utc timestamp in ms. """
        return dt_ms(self._now)

    def tsnext(self):
        return dt_ms(self._now + self.interval)

    def interval_sec(self):
        return self.interval.total_seconds()

    def interval_ms(self):
        return self.interval_sec() * 1000


class EXPeriod():

    def __init__(self, timeframe):
        self.freq = timeframe_to_freq(timeframe)

    def utcms_period(self, ms):
        return pd.Period(datetime.utcfromtimestamp(int(float(ms)/1000)), self.freq)

    def datetime_period(self, dt):
        return pd.Period(dt, self.freq)
