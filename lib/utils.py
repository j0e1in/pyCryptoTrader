from dotenv import load_dotenv
from pprint import pprint
from collections import OrderedDict
from datetime import datetime, timedelta
from pymongo.errors import BulkWriteError, ServerSelectionTimeoutError
from threading import Thread

import asyncio
import ccxt.async as ccxt
import calendar
import functools
import inspect
import logging
import logging.config
import jstyleson as json
import math
import numpy as np
import os
import pandas as pd
import pipes
import sys
import subprocess
import traceback
import uuid

logger = logging.getLogger('pyct')

INF = 9999999
MIN_DT = datetime(1970, 1, 1)
MAX_DT = datetime(9999, 1, 1)


def get_project_root():
    file_dir = os.path.dirname(os.path.abspath(__file__))
    file_dir = os.path.dirname(file_dir)
    return file_dir


def load_json(file):
    with open(file) as f:
        return json.load(f)


def load_config(file):
    _config = load_json(file)

    # Overwrite settings.json if the key
    # is in config
    for env, val in os.environ.items():
        if env.startswith('PYCT_'):
            k = env.split('PYCT_')[1].lower()
            if k in _config:
                _config[k] = val

    return _config

config = load_config('../settings/config.json')

def load_keys(file=None):
    if not file:
        file = config['key_file']

    with open(file) as f:
        return json.load(f)


def load_env(path=None):
    if not path:
        path = '../.env'

    load_dotenv(dotenv_path=path)


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


def tf_td(timeframe):
    """ Convert timeframe to timedelta. """
    if 'D' == timeframe[-1]:
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


def init_ccxt_exchange(ex_id, apikey=None, secret=None, **kwargs):
    """ Return an initialized ccxt API instance. """
    options = {
        'enableRateLimit': True,
        'rateLimit': config['ccxt']['rate_limit'],
        'apiKey': apikey,
        'secret': secret,
    }
    options = combine(options, kwargs)
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


def roundup_dt(dt, td):
    """ Round up datetime object to specified interval,
        eg. min = 20, 10:03 => 10:20 (roundup_dt(dt, min=20))
        eg. sec = 120, 10:00 => 10:02 (roundup_dt(dt, sec=120))
    """
    if isinstance(dt, pd.Timestamp):
        dt = dt.to_pydatetime()

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
        raise ValueError("Invalid parameters")

    return dt + fill - rest


def rounddown_dt(dt, td):
    """ Round up datetime object to specified interval,
        eg. min = 20, 10:03 => 10:20 (roundup_dt(dt, min=20))
        eg. sec = 120, 10:00 => 10:02 (roundup_dt(dt, sec=120))
    """
    if isinstance(dt, pd.Timestamp):
        dt = dt.to_pydatetime()

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
        raise ValueError("Invalid parameters")

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
    if not isinstance(periods, list):
        periods = [periods]

    for p in periods:
        if p[0] >= p[1]:
            return False
    return True


async def execute_mongo_ops(ops):
    if not isinstance(ops, list):
        ops = [ops]
    elif len(ops) == 0:
        return True

    for i, op in enumerate(ops):
        if not isinstance(ops[0], asyncio.Future):
            ops[i] = asyncio.ensure_future(op)

    try:
        res = await asyncio.gather(*ops)
    except (BulkWriteError) as err:

        for msg in err.details['writeErrors']:
            if 'duplicate' in msg['errmsg']:
                continue
            else:
                pprint(err.details)
                raise BulkWriteError(err)
    else:
        return res


async def handle_ccxt_request(func, *args, **kwargs):

    def is_empty_response(err):
        return True if 'empty response' in str(err) else False

    wait = config['ccxt']['wait']
    max_retry = config['request_max_retry']
    succ = False
    count = 0

    while not succ:
        if count > max_retry:
            logger.error(f"{func} exceeds max retry times")
            return None

        count += 1
        try:
            res = await func(*args, **kwargs)

        except (ccxt.RequestTimeout,
                ccxt.DDoSProtection,
                ccxt.ExchangeNotAvailable,
                ccxt.ExchangeError,
                ccxt.InvalidNonce,
                AttributeError,
                KeyError,
                ) as err:

            if isinstance(func, functools.partial):
                func_repr = func.args[0]
            else:
                func_repr = func.__func__.__name__

            # finished fetching all ohlcv
            if is_empty_response(err):
                break

            # server or server-side connection error
            elif isinstance(err, ccxt.ExchangeError):
                logger.warning(f"{func_repr} ExchangeError, {type(err)} {str(err)}")

            elif isinstance(err, ccxt.ExchangeNotAvailable)\
            or   isinstance(err, ccxt.InvalidNonce):
                logger.warning(f"{func_repr} {type(err)}")

            if isinstance(err, functools.partial):
                err_repr = err.__class__.__name__
            else:
                err_repr = err.__class__.__name__

            logger.info(f'# {err_repr} # retry {func_repr} in {wait} seconds...')

            await asyncio.sleep(wait)

        else:
            succ = True

    return res


def filter_by(dicts, conditions, match='all'):
    """ Filter a list of dicts, returning the ones that match certain value.
        Param
            dicts: list of dicts
            conditions: list of (field, field_value) in which a dict will be returned
                       if one/all conditions are matched
            match: 'one' / 'all', if 'one', a dict only need to match one condition
                                  if 'all', a dict need to match every conditions
    """
    def is_match(d, cond):
        return cond[0] in d and d[cond[0]] == cond[1]

    if not isinstance(dicts, list) or (len(dicts) > 0 and not isinstance(dicts[0], dict)):
        raise ValueError(f"`filter_by` requires a list of dicts, not {type(dicts)}")

    if not isinstance(conditions, list):
        conditions = [conditions]

    filtered = []
    for d in dicts:
        all_match = True

        if match == 'all':
            for cond in conditions:
                if not is_match(d, cond):
                    all_match = False
                    break

            if all_match:
                filtered.append(d)

        elif match == 'one':
            for cond in conditions:
                if is_match(d, cond):
                    filtered.append(d)
                    break

    return filtered


def is_within(dt, td):
    """ Return True if dt is occurred with td time."""
    return True if (utc_now() - dt) <= td else False


def smallest_tf(tfs):
    tds = [(idx, tf_td(tf)) for idx, tf in enumerate(tfs)]
    tds.sort(key=lambda tup: tup[1])
    return tfs[tds[0][0]]


def largest_tf(tfs):
    tds = [(idx, tf_td(tf)) for idx, tf in enumerate(tfs)]
    tds.sort(key=lambda tup: -tup[1])
    return tfs[tds[0][0]]


def alert_sound(duration, words, n=1):
    """ Play aler sound for N seconds.
        Require some dependencies.
        Ubuntu: $ sudo apt install sox
        Windows: $ pip install winsound
        OSX: $ Built-in speech
    """
    freq = 500  # Hz

    for _ in range(n):

        if sys.platform == "linux" or sys.platform == "linux2":  # linux
            # sudo apt install sox
            os.system(f"play --no-show-progress --null --channels 1 synth {duration} sine {freq}")
        elif sys.platform == "darwin":  # OS X
            os.system(f"say {words}")
        elif sys.platform == "win32":  # Windows
            import winsound
            winsound.Beep(freq, duration * 1000)
        else:
            logger.warning(f"Platform {sys.platform} is not supported.")


def ohlcv_to_interval(ohlcv, src_tf, target_td):
    """ Convert ohlcv to higher interval (timeframe). """
    src_td = tf_td(src_tf)

    if target_td < timedelta(hours=1):
        tmax = 60 # timeframe is under 1 hour
    elif target_td < timedelta(days=1):
        tmax = 24 #  timeframe is under 1 day

    if target_td < src_td:
        raise ValueError(f"Target interval {target_td} < original interval {src_td}")

    if (target_td % src_td).seconds != 0:
        raise ValueError(f"Target interval {target_td} is not a multiple of original interval {src_td}")

    if target_td == src_td:
        return ohlcv

    def gen_target_dt_index(ohlcv, target_td):
        start = ohlcv.index[0]
        end = ohlcv.index[-1]
        std = timedelta(hours=start.hour, minutes=start.minute, seconds=start.second)
        etd = timedelta(hours=end.hour, minutes=end.minute, seconds=end.second)

        start = start - (std % target_td)
        end = end - (etd % target_td)
        cur = start

        index = []
        while cur <= end:
            index.append(cur)
            prev = cur
            cur += target_td

            if tmax == 60 and (prev.minute + target_td.seconds/60) > tmax:
                cur -= timedelta(minutes=cur.minute)
            elif tmax == 24 and (prev.hour + target_td.seconds/60/60) > tmax:
                cur -= timedelta(hours=cur.hour)

        return index

    target_index = gen_target_dt_index(ohlcv, target_td)
    target_ohlcv = pd.DataFrame(columns=ohlcv.columns, index=target_index, dtype=float)
    target_ohlcv.index.name = ohlcv.index.name

    for start in target_ohlcv.index:
        end = start + target_td

        if tmax == 60 and (start.minute + target_td.seconds/60) > tmax:
            end -= timedelta(minutes=end.minute)
        elif tmax == 24 and (start.hour + target_td.seconds/60/60) > tmax:
            end -= timedelta(hours=end.hour)

        end -= timedelta(seconds=1)

        if len(ohlcv[start:end]) > 0:
            target_ohlcv.loc[start].open    = ohlcv[start:end].open[0]
            target_ohlcv.loc[start].close   = ohlcv[start:end].close[-1]
            target_ohlcv.loc[start].high    = ohlcv[start:end].high.max()
            target_ohlcv.loc[start].low     = ohlcv[start:end].low.min()
            target_ohlcv.loc[start].volume  = ohlcv[start:end].volume.sum()

    target_ohlcv = target_ohlcv.dropna()

    return target_ohlcv


def print_to_file(data, path):
    import errno

    def mkdir_p(path):
        try:
            os.makedirs(path)
        except OSError as exc:  # Python >2.5
            if exc.errno == errno.EEXIST and os.path.isdir(path):
                pass
            else:
                raise

    mkdir_p(os.path.dirname(path))

    with open(path, 'w+') as f:
        pprint(data, stream=f)


def is_valid_tf(tf):
    base = tf[-1]
    num = tf[:-1]

    if base not in ['m', 'h', 'd'] \
    or not num.isdigit():
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


log_type = 'pyct_colored'

if config['mode'] == 'debug':
    addition_info = "\t  (%(filename)s @ %(funcName)s:%(lineno)d)"
else:
    addition_info = ""

log_config = dict(
    version = 1,
    # disable_existing_loggers = False,
    formatters = {
        'pyct_default': { # has alignment but no color
            'datefmt': "%Y-%m-%d %H:%M:%S",
            'format': f"%(asctime)s | %(levelname)-8s | %(message)s{addition_info}"
        },
        'pyct_colored': { # has color but no alignment
            'class': 'chromalog.log.ColorizingFormatter',
            'datefmt': "%Y-%m-%d %H:%M:%S",
            'format': f"%(asctime)s | %(levelname)s | %(message)s{addition_info}"
        }
    },
    handlers = {
        'pyct_default': {
            'class': 'logging.StreamHandler',
            'formatter': 'pyct_default'
        },
        'pyct_colored': {
            'class': 'chromalog.log.ColorizingStreamHandler',
            'formatter': 'pyct_colored'
        }
    },
    loggers = {
        # '': {
        #     'handlers': [log_type],
        #     'level': 'DEBUG' \
        #         if config['mode'] != 'production' \
        #         else 'INFO',
        #     'propagate': False
        # },
        'pyct': {
            'handlers': [log_type], # switch between default and colored handlers
            'level': 'DEBUG' \
                if config['mode'] != 'production' \
                else 'INFO',
            'propagate': False
        },
        'ccxt': {
            'handlers': [log_type],
            'level': 'INFO',
            'propagate': False
        },
        'root': {} # sanic root logger (gathers all sanic logs)
    }
)

logging.config.dictConfig(log_config)


def register_logging_file_handler(log_file, log_config):
    """ Register file handler to all loggers. """
    fh = logging.FileHandler(log_file, mode='a')
    fh.setFormatter(
        logging.Formatter(log_config['formatters']['pyct_default']['format'],
                          log_config['formatters']['pyct_default']['datefmt']))

    for log in log_config['loggers']:
        logging.getLogger(log).addHandler(fh)


def run_async_in_thread(func, *args, **kwargs):

    def run_async(func, loop, *args, **kwargs):
        loop.run_until_complete(func(*args, **kwargs))

    loop = asyncio.new_event_loop()
    th = Thread(target=run_async, args=(func, loop, *args), kwargs=kwargs)
    th.start()

    return th

def catch_traceback(fn, *args, **kwargs):
    """ Wraps `fn` in order to preserve the
        traceback of any kind of exception.
    """
    try:
        return fn(*args, **kwargs)
    except Exception:
        raise sys.exc_info()[0](traceback.format_exc())


async def async_catch_traceback(fn, *args, **kwargs):
    """ Wraps `fn`(coroutine) in order to preserve the
        traceback of any kind of exception.
    """
    try:
        return await fn(*args, **kwargs)
    except Exception:
        raise sys.exc_info()[0](traceback.format_exc())


def is_price_valid(start_price, end_price, side):
    if start_price is None and end_price is None:
        return True

    invalid =  (end_price and not start_price) \
            or (start_price is 0 or end_price is 0) \
            or (start_price < end_price and side == 'buy') \
            or (start_price > end_price and side == 'sell')

    return not invalid


def periodic_routine(fn, interval, *args, **kwargs):
    """ Convert a function into a endless while loop
        that is executed every `interval` seconds.
    """
    async def routinized(fn, interval, *args, **kwargs):
        while True:
            if asyncio.iscoroutinefunction(fn):
                await fn(*args, **kwargs)
            else:
                fn(*args, **kwargs)

            await asyncio.sleep(interval)

    return routinized(fn, interval, *args, **kwargs)


def true_symbol(ex, symbol):
    """ Convert a symbol to ccxt-compatiable version. """
    if not symbol:
        return symbol

    if symbol not in ex.symbols:
        # Check if USD is named 'USDT'
        if symbol.split('/')[1] == 'USD' \
        and symbol + 'T' in ex.symbols:
            symbol += 'T'
        else:
            raise ValueError(f"'{ex.id}' has no symbol '{symbol}'")
    return symbol


def remote_exists(host, path, ssh_options=''):
    """ Test if a file exists at path on a host accessible with SSH. """
    status = subprocess.call(
        ['ssh', ssh_options, host, 'test -f {}'.format(pipes.quote(path))])
    if status == 0:
        return True
    if status == 1:
        return False
    raise RuntimeError('SSH failed')


def get_remote_cpu_usage(host):
    cmd = ["ssh", host, "top", "-bn", "2", "-d", "1", "|",
           "grep", "'^%Cpu'", "|", "tail", "-n", "1", "|",
           "awk", "'{print $2+$4+$6}'"]
    output = subprocess.check_output(' '.join(cmd), shell=True)
    try:
        return float(output.decode('utf-8').strip())
    except ValueError:
        logger.error(
            f"Could not convert string to float: {output.decode('utf-8').strip()}"
        )
        return np.nan
