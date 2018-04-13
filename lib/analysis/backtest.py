from asyncio import ensure_future
from collections import OrderedDict
from datetime import timedelta
from multiprocess import Process, Queue
import asyncio
import copy
import itertools
import random
import logging
import queue
import pandas as pd
import numpy as np

from analysis.backtest_trader import SimulatedTrader, FastTrader
from utils import \
    INF, \
    MIN_DT, \
    MAX_DT, \
    config, \
    Timer, \
    tf_td, \
    utc_now, \
    roundup_dt, \
    rounddown_dt, \
    check_periods

try:
    from analysis.plot import Plot
except ImportError:
    pass

from db import EXMongo

from pprint import pprint

logger = logging.getLogger('pyct')

# import multiprocessing, logging
# logger = multiprocessing.log_to_stderr()
# logger.setLevel(multiprocessing.SUBDEBUG)

class Backtest():

    def __init__(self, strategy, data_feed, start, end,
                 enable_plot=False,
                 custom_config=None):

        if not data_feed:
            raise ValueError(f"Data feed is empty")

        _config = custom_config or config
        self._config = _config
        self.config = _config['backtest']
        self.strategy = strategy
        self.enable_plot = enable_plot
        self.ohlcvs = data_feed['ohlcvs']
        self.trades = data_feed['trades']
        self.start = start
        self.end = end
        self.timer = Timer(self.start, self.config['base_timeframe'])

        if self.config['fast_mode']:
            self.trader = FastTrader(self.timer, self.strategy, custom_config=_config)
            self.trader.fast_mode = True
            self.strategy.fast_mode = True
        else:
            self.trader = SimulatedTrader(self.timer, self.strategy, custom_config=_config)

        for ex in self.trader.markets:
            avail_markets = list(data_feed['ohlcvs'][ex].keys())

            for market in self.trader.markets[ex]:
                if market not in avail_markets:
                    raise ValueError(f"Data feed has no market {market}")

        self.strategy.init(self.trader)

    def run(self):
        self.report = self._init_report()

        if self.config['fast_mode']:
            # Feed all data at once and accept and execute a sequence of orders
            self.fast_run()

        else:
            # Feed data by base timeframe, is same as oneline strategy trading,
            # also stricts stratgy from cheating.
            self.slow_run()

        self._analyze_orders()
        self.clean_order_history()

        if self.enable_plot:
            self.plot_result()

        return self.report

    def fast_run(self):
        self.trader.feed_data(self.end, self.ohlcvs)
        self.trader.tick()
        self.trader.liquidate()

    def slow_run(self):
        # Feed one day data to trader to let strategy has initial data to setup variables
        pre_feed_end = self.start + timedelta(days=self.strategy.prefeed_days)
        self.trader.feed_data(pre_feed_end, self.ohlcvs)
        self.strategy.prefeed()

        # Feed the rest of data and tell trader to execute orders
        cur_time = self.timer.now()
        while cur_time < self.end:
            cur_time = self.timer.now()
            next_time = self.timer.next()
            self.trader.feed_data(next_time, self.ohlcvs)
            self.trader.tick()  # execute orders

        self.trader.liquidate()

    def _init_report(self):
        self.margin_PLs = []
        return {
            "initial_fund": copy.deepcopy(self.trader.wallet),
            "initial_value": self._calc_total_value(self.timer.now()),
            "final_fund": None,
            "final_value": 0,
            "days": (self.end - self.start).days,
            "PL": 0,
            "PL(%)": 0,
            "PL_Eff": 0,
            "#_profit_trades": 0,
            "#_loss_trades": 0,
        }

    def _analyze_orders(self):
        # Calculate total PL
        self.report['final_fund'] = copy.deepcopy(self.trader.wallet)
        self.report['final_value'] = self._calc_total_value(self.timer.now())
        self.report['PL'] = self.report['final_value'] - self.report['initial_value']
        self.report['PL(%)'] = self.report['PL'] / self.report['initial_value'] * 100
        self.report['Fee'] = 0

        # PL_Eff = 1 means 100% return in 30 days
        self.report['PL_Eff'] = self.report['PL(%)'] / (self.end - self.start).days * 0.3

        for ex, orders in self.trader.order_history.items():
            for _, order in orders.items():
                if not order['canceled']:

                    self.report['Fee'] += order['fee']

                    if order['margin']:
                        self.report['Fee'] += order['margin_fee']

                        self.margin_PLs.append(order['PL'])

                        # Calculate number of profit/loss trades
                        if order['PL'] >= 0:
                            self.report['#_profit_trades'] += 1
                        else:
                            self.report['#_loss_trades'] += 1

                    # TODO: Add PL calculations for normal order

    def _calc_total_value(self, dt):
        # TODO: Add conversion to BTC than to USD for exchanges that don't have USD pairs.

        total_value = 0
        for ex, wallet in self.trader.wallet.items():
            for curr, amount in wallet.items():

                min_tf = self.trader.timeframes[ex][0]
                dt = roundup_dt(dt, tf_td(min_tf))

                if curr == 'USD':
                    total_value += amount
                else:
                    market = '/'.join([curr, 'USD'])
                    ohlcv = self.ohlcvs[ex][market][min_tf]

                    if len(ohlcv) is 0:
                        raise RuntimeError(f"ohlcv is empty for period \"{self.start}\" to \"{self.end}\"")

                    dt = ohlcv.index[-1] if dt > ohlcv.index[-1] else dt

                    if len(ohlcv[:dt]) == 0:
                        # if no ohlcv exists before this datetime,
                        # select the first ohlcv
                        ohlcv = ohlcv.iloc[0]
                    else:
                        # else the last ohlcv of this datetime
                        ohlcv = ohlcv[:dt].iloc[-1]

                    price = ohlcv.close
                    total_value += amount * price

        return total_value

    def plot_result(self):
        """ Plot ohlcv and orders. """
        plot = Plot(custom_config=self._config)

        for ex, markets in self.ohlcvs.items():
            for market, tfs in markets.items():

                # Plot ohlc
                ohlc = self.ohlcvs[ex][market][self.trader.config['indicator_tf']]
                plot.plot_ohlc(ohlc)

                # Plot orders
                orders = self.get_order_history_by_market(ex, market)
                plot.plot_order_annotation(orders, ohlc)

        plot.tight_layout()
        plot.show()

    def get_order_history_by_market(self, ex, market):
        """ Return order history of a market. """
        orders = []
        for ord in list(self.trader.order_history[ex].values()):
            if ord['market'] == market:
                orders.append(ord)
        return orders

    def clean_order_history(self):
        """ Remove fields starts with 'op_' from order history. """
        for _, orders in self.trader.order_history.items():
            for _, order in orders.items():
                fields = list(order.keys())
                for field in fields:
                    if field.find('op_') >= 0:
                        del order[field]


class BacktestRunner():
    """
        Fixed test period: [(start, end), (start, end), ...]
        Randomize test: window size range, number of tests
        Fixed windows size with shift by step: window size, shift step

    """

    def __init__(self, strategy, data_feed, custom_config=None):
        self._config = custom_config or config
        self.strategy = strategy
        self.data_feed = data_feed

    async def run_periods(self, periods):
        """
            Param
                periods: array, [(start, end), (start, end), ...]
        """
        if not isinstance(periods, list):
            periods = [periods]

        reports = []
        reports_q = Queue(self._config['max_processes'])
        ps = queue.Queue(self._config['max_processes'])
        n_reports_left = len(periods)

        def run_backtest(backtest):
            report = backtest.run()
            reports_q.put({
                'period': (backtest.start, backtest.end),
                'report': report
            })
            del backtest

        for start, end in periods:
            backtest = await Backtest(self.strategy, self.data_feed, start, end,
                enable_plot=False, custom_config=self._config)

            if self._config['use_multicore']:
                if ps.full():
                    reports.append(reports_q.get())
                    ps.get().join()
                    n_reports_left -= 1

                p = Process(target=run_backtest, args=(backtest,))
                p.start()
                ps.put(p)

            else:  # use single core
                if reports_q.full():
                    reports.append(reports_q.get())
                    n_reports_left -= 1

                run_backtest(backtest)

        # Results queued by processes must be cleared from the queue,
        # or some processes will not terminate.
        for _ in range(n_reports_left):
            reports.append(reports_q.get())

        # Wait for all processes to terminate
        # (should be unecessary here because getting reports already blocks)
        if self._config['use_multicore']:
            while ps.qsize() > 0:
                ps.get().join()

        summary = self._analyze_reports(reports)
        return summary

    @staticmethod
    def _analyze_reports(reports):
        if not isinstance(reports, list):
            reports = [reports]

        summary = pd.DataFrame(columns=['start', 'end', 'days',
                                        '#P', '#L', 'PL(%)', 'PL_Eff'])
        for rep in reports:
            dt = rep['period']
            report = rep['report']

            summ = {
                'start': dt[0],
                'end': dt[1],
                'days': report['days'],
                '#P': report['#_profit_trades'],
                '#L': report['#_loss_trades'],
                'PL(%)': report['PL(%)'],
                'PL_Eff': report['PL_Eff'],  # PL_Eff = 1 means 100% return / 30days
            }
            summary = summary.append(summ, ignore_index=True)

        return summary

    @staticmethod
    def generate_random_periods(start, end, period_size_range, num_test):
        """
            Param
                start: datetime
                end: datetime
                period_size_range: tuple, (int, int), the fist int must < the second
                    and the second int should < (end - start) / 2
                num_test: int, number of test periods to generate

        """
        if period_size_range[0] > period_size_range[1]:
            raise ValueError("period_size_range's first number should >= the second one")

        if (end - start).days / 1.5 < period_size_range[1]:
            raise ValueError(f"{period_size_range[1]} days period size is too large "
                             f"for {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}, "
                             f"try size <= {int((end - start).days / 1.5)}")

        periods = []

        i = 0
        while i < num_test:
            d = random.randint(period_size_range[0], period_size_range[1])
            period_size = timedelta(days=d)

            days_diff = (end - start).days - period_size.days

            if days_diff < 1:
                continue

            _start = start + timedelta(days=random.randint(1, days_diff))
            _end = _start + period_size

            # Restart if the period has been tested
            if (_start, _end) in periods:
                continue

            periods.append((_start, _end))
            i += 1

        return periods

    @staticmethod
    def generate_periods_with_shift_step(start, end, period_size, shift_step):
        """
            Param
                start: datetime
                end: datatime
                period_size: int, days
                shift_step: int, days
        """
        periods = []

        period_size_td = timedelta(days=period_size)
        shift_step_td = timedelta(days=shift_step)

        cur_start = start
        cur_end = cur_start + period_size_td

        while cur_end <= end:
            periods.append((cur_start, cur_end))
            cur_start += shift_step_td
            cur_end += shift_step_td

        return periods


class ParamOptimizer():
    """ Try every parameters combinations in config['params'] to find best ones. """

    # TODO: Change optimizer to run all params in one period to reuse data and enable multicore

    def __init__(self, mongo, strategy, custom_config=None):
        self._config = custom_config or config
        self.mongo = mongo
        self.strategy = strategy
        self.params = self._config['analysis']['params']['common']

        self._init_param_queue()

    def _init_param_queue(self):
        """ Use default values to create a param queue
            in case some params' range or selections are not set by user.
        """
        self.param_d = OrderedDict()
        for k, v in self.params.items():
            self.param_d[k] = [v]

    def optimize_range(self, param_name, start, end, step):
        """ Set optimization range for numerical params. """
        if start > end:
            raise ValueError(f"start must < end")

        if param_name in self.params:
            self.param_d[param_name] = np.arange(start, end+step/INF, step)
        else:
            raise ValueError(f"{param_name} is not in config['parmas']")

    def optimize_selection(self, param_name, selections):
        """ Set optimization selections for non-numerical params, eg. '1m', '5m', ... """
        if not isinstance(selections, list):
            raise TypeError("selections should be a list")

        if param_name in self.params:
            self.param_d[param_name] = selections
        else:
            raise ValueError(f"{param_name} is not in config['parmas']")

    def count(self):
        n = 1
        for k in self.param_d:
            n *= len(self.param_d[k])
        return n

    def get_combinations(self, f=None):
        return gen_combinations_large(
            self.param_d.values(),
            columns=self.param_d.keys(),
            to_file=f)

    async def run(self, combs, period, ex, market, name=''):

        reports_q = Queue(self._config['max_processes'])
        ps = queue.Queue(self._config['max_processes'])
        n_reports_left = len(combs)

        def run_backtest(backtest, idx):
            report = backtest.run()
            reports_q.put([idx, report])
            del backtest

        if not check_periods(period):
            raise ValueError("Periods is invalid.")

        _config = copy.deepcopy(self._config)

        # Find last checkpoint to resume
        tf = _config['analysis']['indicator_tf']
        last_idx = await self.last_checkpoint(name, ex, market, tf, period)

        # Remove other exchanges
        _config['analysis']['exchanges'] = {
            ex: _config['analysis']['exchanges'][ex]
        }

        # Remove other markets
        _config['analysis']['exchanges'][ex]['markets'] = [market]

        start, end = period
        num_tests = len(combs) - last_idx
        logger.info(f"Running {ex} {market} {start}->{end} "
                    f"optimization with << {num_tests} >> tests.")

        logger.info(f"Starting from param set {last_idx+1}")

        # Construct data_feed request
        req = {}
        exs = _config['analysis']['exchanges']
        for ex in exs:
            symbols = exs[ex]['markets']
            timeframes = exs[ex]['timeframes']
            if _config['analysis']['indicator_tf'] not in timeframes:
                timeframes += [_config['analysis']['indicator_tf']]
            req[ex] = {
                'symbols': symbols,
                'timeframes': timeframes,
            }

        data_feed = await get_data_feed(self.mongo, req, start, end)
        info = {
            'name': name,
            'ex': ex,
            'symbol': market,
            'tf': _config['analysis']['indicator_tf'],
            'datetime': roundup_dt(utc_now(), timedelta(minutes=1)),
            'start': start,
            'end': end,
        }
        reports = []
        count = 0

        # Start optimization
        for idx, row in combs.iterrows():
            if idx <= last_idx: # skip backtested params
                n_reports_left -= 1
                continue

            params = OrderedDict(row.to_dict())
            _config['analysis']['params'][market] = params

            self.strategy.set_config(_config)
            backtest = Backtest(self.strategy, data_feed, start, end,
                enable_plot=False, custom_config=_config)

            if ps.full():
                reports.append(reports_q.get())
                n_reports_left -= 1
                ps.get().join()

            if self._config['use_multicore']:
                p = Process(target=run_backtest, args=(backtest, idx))
                p.start()
                ps.put(p)
            else: # for debugging
                if reports_q.full():
                    reports.append(reports_q.get())
                    n_reports_left -= 1

                run_backtest(backtest, idx)

            num_tests -= 1
            count += 1
            if count == 1000: # periodically log number of remaining tests
                count = 0
                logger.info(f"{num_tests} tests remaining")

            if len(reports) >= 1000:
                await self.save_reports(name, reports, info)
                await self.update_optimization_meta(name, ex, market, tf, period,
                                                    last_idx=reports[-1][0])
                reports = []

        while n_reports_left > 0:
            reports.append(reports_q.get())
            n_reports_left -= 1

        await self.save_reports(name, reports, info)
        await self.update_optimization_meta(name, ex, market, tf, period,
                                            last_idx=reports[-1][0])

        # Wait for all processes to terminate
        # (should be unecessary here because getting reports already blocks)
        if self._config['use_multicore']:
            while ps.qsize() > 0:
                ps.get().join()

    async def save_reports(self, name, reports, info):

        def parse_report(report):
            return {
                'days': report['days'],
                'PL(%)': report['PL(%)'],
                'PL_Eff': report['PL_Eff'],
            }

        if not reports:
            return

        if not isinstance(reports, list):
            reports = [reports]

        thresh = self._config['analysis']['param_optmization_save_threshold']
        parsed = []

        for report in reports:
            idx = report[0]
            rep = report[1]

            if rep['PL(%)'] >= thresh:
                parsed.append({
                    **info,
                    **parse_report(rep),
                    **{'param_idx': idx},
                })

        # Save high PL params
        if parsed:
            coll = self.mongo.get_collection(
                self.mongo.config['dbname_analysis'],
                f'param_optimization_{name}')
            await coll.insert_many(parsed)

    async def last_checkpoint(self, name, ex, symbol, tf, period):
        coll = self.mongo.get_collection(
            self.mongo.config['dbname_analysis'], f'param_optimization_{name}')

        # Find backtests that are within optimization_delay days
        res = await coll.find({
            'name': name,
            'ex': ex,
            'symbol': symbol,
            'tf': tf,
            'datetime': {'$gte': period[1] -
                timedelta(days=self._config['analysis']['optimization_delay'])}
        }).sort([('param_idx', -1)]).limit(1).to_list(length=INF)

        return res[0]['param_idx'] if res else 0

    async def update_optimization_meta(self, name, ex, symbol, tf, period, last_idx):
        coll_opt_meta = self.mongo.get_collection(
            self.mongo.config['dbname_analysis'], 'param_optimization_meta')

        best_param, pl = await self.get_best_param(name, ex, symbol, tf, period)

        if best_param:
            await coll_opt_meta.update_one(
                {'name': name, 'ex': ex, 'symbol': symbol, 'tf': tf},
                {'$set': {
                    **{'name': name, 'ex': ex, 'symbol': symbol, 'tf': tf},
                    **{'best_param': best_param,
                       'PL(%)': pl,
                       'datetime': rounddown_dt(utc_now(), timedelta(minutes=1)),
                       'last_backtest_idx': last_idx}
                }}, upsert=True)

    async def get_best_param(self, name, ex, symbol, tf, period):

        # Get best PL param index
        coll = self.mongo.get_collection(
            self.mongo.config['dbname_analysis'], f'param_optimization_{name}')
        best_result = await coll.find({
            'name': name,
            'ex': ex,
            'symbol': symbol,
            'tf': tf,
            'datetime': {'$gte': period[1] -
                timedelta(days=self._config['analysis']['optimization_delay'])}
        }).sort([('PL(%)', -1)]).limit(1).to_list(length=INF)

        if not best_result: return [], 0

        coll = self.mongo.get_collection(
            self.mongo.config['dbname_analysis'], f'param_set_{name}')
        params = await coll.find_one({'idx': best_result[0]['param_idx']})

        if not params: return [], 0

        coll = self.mongo.get_collection(
            self.mongo.config['dbname_analysis'], f'param_set_meta')
        meta = await coll.find_one({'name': name})

        if not meta: return [], 0

        p = {col: val for col, val in zip(meta['columns'], params['params'])}

        return p, best_result[0]['PL(%)']


def gen_combinations(arrays, columns=None, types=None):
    """ Generate all combinations from multiple arrays and returns a DataFrame.
        Param
            arrays: list of lists (all elements in a sub list must have same data type)
            columns: list of column names
            types: list of types for each column
    """
    combs = list(itertools.product(*arrays))
    df = pd.DataFrame(combs, columns=columns)

    for k, t in types.items():
        df[k] = df[k].astype(t)

    return df


def gen_combinations_large(arr, columns=None, to_file=None):
    """ Generate large number of combinations without memory limitations. """
    pos = np.zeros(len(arr))

    if not isinstance(arr, list):
        arr = list(arr)

    if to_file:
        to_file.write(','.join(map(str, columns)) + '\n')

    n_combs = 1

    for i in range(len(arr)):
        n_combs *= len(arr[i])

    for _ in range(n_combs):

        cc = []
        for i in range(len(arr)):
            cc.append(arr[i][int(pos[i])])

        if to_file:
            to_file.write(','.join(map(str, cc)) + '\n')
        else:
            yield cc

        for i in range(len(arr)):
            if pos[i] < len(arr[i]) - 1:
                pos[i] += 1
                break
            else:
                pos[i] = 0


def get_types(d):
    """ Get data types for each field in a dict. """
    dtypes = {}

    for k, v in d.items():
        if isinstance(v, list) or isinstance(v, np.ndarray):
            dtypes[k] = type(v[0])
        else:
            dtypes[k] = type(v)
    return dtypes


async def get_data_feed(mongo, req, start=None, end=None, trades=False):
    """ Read ohlcv and trades(optional) from mongodb.
        Param
            req: {
                'bitfinex': {
                    'symbols': [...],
                    'timeframes: [...]
                },
                ...
            }
            start: datatime
            end: datatime
    """
    start = start or MIN_DT
    end = end or MAX_DT

    if start >= end:
        raise ValueError("Start datatime must < end")

    data_feed = {'ohlcvs': {}, 'trades': {}}

    for ex in req:
        syms = req[ex]['symbols']
        tfs = req[ex]['timeframes']
        data_feed['ohlcvs'][ex] = await mongo.get_ohlcvs_of_symbols(ex, syms, tfs, start, end)

        if trades:
            data_feed['trades'][ex] = await mongo.get_trades_of_symbols(ex, syms, start, end)

    return data_feed