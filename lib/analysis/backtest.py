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
    config, \
    Timer, \
    tf_td, \
    roundup_dt, \
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

# TODO: reuse data for multiple tests, don't read data everytime


class Backtest():

    def __init__(self, mongo):
        self.mongo = mongo

    async def init(self, **options):
        """ Can be used to reset and run tests with different options.
            Param
                options: {
                    'strategy': a strategy object
                    'start': datetime
                    'end': datetime
                    'enable_trade_feed': bool, default is False (optional)
                                         Turn on trade feed if strategy requires it
                    'custom_config': (optional) JSON, loaded config
                }
        """
        self._set_init_options(**options)
        self.strategy.init(self.trader)

        await self._get_all_data()
        self.start, self.end = self.get_real_start_end()

        return self

    def _set_init_options(self, **options):
        if 'custom_config' in options:
            _config = options['custom_config']
        else:
            _config = config

        self.strategy = options['strategy']
        self.start = options['start']
        self.end = options['end']

        if self.start >= self.end:
            raise ValueError(f"backtest start datetime must > end")

        if 'enable_trade_feed' in options:
            self.enable_trade_feed = options['enable_trade_feed']
        else:
            self.enable_trade_feed = False

        self.config = _config['backtest']
        self.timer = Timer(self.start, self.config['base_timeframe'])

        if self.config['fast_mode']:
            self.trader = FastTrader(self.timer, self.strategy, custom_config=_config)
            self.trader.fast_mode = True
            self.strategy.fast_mode = True
        else:
            self.trader = SimulatedTrader(self.timer, self.strategy, custom_config=_config)

        if 'enable_plot' in options:
            self.enable_plot = options['enable_plot']
        else:
            self.enable_plot = _config['matplot']['enable']

        if self.enable_plot:
            self.plot = Plot(custom_config=_config)

        self.markets = self.trader.markets
        self.timeframes = self.trader.timeframes

    async def _get_all_data(self):
        self.ohlcvs = {}
        self.trades = {}
        for ex, markets in self.markets.items():
            self.ohlcvs[ex] = await self.mongo.get_ohlcvs_of_symbols(ex, markets, self.timeframes[ex], self.start, self.end)

            if self.enable_trade_feed:
                self.trades[ex] = await self.mongo.get_trades_of_symbols(ex, markets, self.start, self.end)

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

                min_tf = self.timeframes[ex][0]
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
        for ex, markets in self.ohlcvs.items():
            for market, tfs in markets.items():

                # Plot ohlc
                ohlc = self.ohlcvs[ex][market][self.trader.config['indicator_tf']]
                self.plot.plot_ohlc(ohlc)

                # Plot orders
                orders = self.get_order_history_by_market(ex, market)
                self.plot.plot_order_annotation(orders, ohlc)

        self.plot.tight_layout()
        self.plot.show()

    def get_order_history_by_market(self, ex, market):
        orders = []
        for ord in list(self.trader.order_history[ex].values()):
            if ord['market'] == market:
                orders.append(ord)
        return orders

    def get_real_start_end(self):
        """ Get real start and end of ohlcv rather than using that are requested by user. """
        start = self.end
        end = self.start

        for ex, markets in self.markets.items():
            for market in markets:

                if len(self.ohlcvs[ex][market]['1m']) is 0:
                    raise RuntimeError(f"No ohlcv in {ex} {market} '1m' from {start} to {end}")

                dt = self.ohlcvs[ex][market]['1m'].index[0]
                if dt < start:
                    start = dt

                dt = self.ohlcvs[ex][market]['1m'].index[-1]
                if dt > end:
                    end = dt

        return start, end

    def clean_order_history(self):
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

    def __init__(self, mongo, strategy, multicore=True, custom_config=None):
        self._config = custom_config if custom_config is not None else config

        self.mongo = mongo
        self.strategy = strategy
        self.multicore = multicore

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
            days = (opts['end'] - opts['start']).days

            if self._config['mode'] == 'debug':
                logger.debug(f"Backtesting {opts['start']} / {opts['end']} ({days} days)")

            report = backtest.run()
            reports_q.put({
                'period': (backtest.start, backtest.end),
                'report': report
            })
            del backtest

        for start, end in periods:
            opts = {
                'strategy': self.strategy,
                'start': start,
                'end': end,
                'enable_plot': False,
                'custom_config': self._config
            }

            backtest = await Backtest(self.mongo).init(**opts)

            if self.multicore and self._config['use_multicore']:
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
        self._config = custom_config if custom_config else config
        self.params = self._config['analysis']['params']['common']

        self.mongo = mongo
        self.strategy = strategy

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

    def get_combinations(self):
        return gen_combinations(
            self.param_d.values(),
            columns=self.param_d.keys(),
            types=get_types(self.param_d))

    def get_combinations_large(self, f):
        return gen_combinations_large(
            self.param_d.values(),
            columns=self.param_d.keys(),
            to_file=f)

    async def run(self, combs, periods):
        if not check_periods(periods):
            raise ValueError("Periods is invalid.")

        config = copy.deepcopy(self._config)

        num_tests = len(combs) * len(periods)
        logger.info(f"Running optimization with << {num_tests} >> tests.")

        summaries = []

        count = 0
        for i in range(len(combs)):
            params = OrderedDict(combs.iloc[i].to_dict())
            config['analysis']['params']['common'] = params

            self.strategy.set_config(config)

            bt_runner = BacktestRunner(self.mongo, self.strategy, custom_config=config)
            summaries.append({
                'params': params,
                'summary': await bt_runner.run_periods(periods)
            })

            num_tests -= len(periods)
            count += len(periods)
            if count >= 10: # periodically log number of remaining tests
                count = 0
                logger.info(f"{num_tests} tests remaining")

        return summaries

    @staticmethod
    def analyze_summary(summaries, summary_type):
        """
            Param
                summaries: list of dicts returned by ParamOptimizer.run()
                summary_type: one of the options provided, eg. 'best_params'
        """
        if summary_type == 'best_params':
            cols = list(summaries[0]['params'].keys()) + list(summaries[0]['summary'])
            df = pd.DataFrame(columns=cols)
            params_df = pd.DataFrame(columns=list(summaries[0]['params'].keys()))

            for summ in summaries:
                params = summ['params']
                summary = summ['summary']

                tmp_df = params_df.append(params, ignore_index=True)

                for i in range(len(summary)-1):
                    tmp_df = tmp_df.append(tmp_df.iloc[0].copy(), ignore_index=True)

                tmp_df = pd.concat([tmp_df, summary], axis=1)
                df = df.append(tmp_df, ignore_index=True)

            df.sort_values(by='PL_Eff', ascending=False, inplace=True)
            return df

        # TODO: use multi-core for testing multiple params


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

    # from ipdb import set_trace; set_trace()
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
