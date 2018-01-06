from collections import OrderedDict
from datetime import timedelta
from multiprocess import Process, Queue, cpu_count
import copy
import random
import logging
import pandas as pd
import queue

from utils import config, Timer, roundup_dt, timeframe_timedelta
from trader import SimulatedTrader, FastTrader
from plot import Plot
from db import EXMongo

from pprint import pprint
from ipdb import set_trace as trace

logger = logging.getLogger()

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
        return self

    def reset(self):
        self.trader.reset()
        self.strategy.init(self.trader)

    def _set_init_options(self, **options):
        if 'custom_config' in options:
            _config = options['custom_config']
        else:
            _config = config

        self.strategy = options['strategy']
        self.start = options['start']
        self.end = options['end']

        if 'enable_trade_feed' in options:
            self.enable_trade_feed = options['enable_trade_feed']
        else:
            self.enable_trade_feed = False

        self.config = _config['backtest']
        self.timer = Timer(self.start, self.config['base_timeframe'])

        if self.config['fast_mode']:
            self.trader = FastTrader(self.timer, self.strategy, _config)
            self.trader.fast_mode = True
            self.strategy.fast_mode = True
        else:
            self.trader = SimulatedTrader(self.timer, self.strategy, _config)

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
        return {
            "initial_fund": copy.deepcopy(self.trader.wallet),
            "initial_value": self._calc_total_value(self.timer.now()),
            "final_fund": None,
            "final_value": 0,
            "days": (self.end - self.start).days,
            "PL": 0,
            "PL(%)": 0,
            "PL_Eff": 0,
            "margin_PLs": [],
            "#_profit_trades": 0,
            "#_loss_trades": 0,
        }

    def _analyze_orders(self):
        # Calculate total PL
        self.report['final_fund'] = copy.deepcopy(self.trader.wallet)
        self.report['final_value'] = self._calc_total_value(self.timer.now())
        self.report['PL'] = self.report['final_value'] - self.report['initial_value']
        self.report['PL(%)'] = self.report['PL'] / self.report['initial_value'] * 100

        # PL_Eff = 1 means 100% return in 30 days
        self.report['PL_Eff'] = self.report['PL(%)'] / (self.end - self.start).days * 0.3

        for ex, orders in self.trader.order_history.items():
            for _, order in orders.items():
                if order['margin'] and not order['canceled']:
                    self.report['margin_PLs'].append(order['PL'])

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
                sec = timeframe_timedelta(min_tf).total_seconds()
                dt = roundup_dt(dt, sec=sec)

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

                # Get timeframe to plot ohlc
                if market in self.plot.config['plot_timeframes']:
                    tf = self.plot.config['plot_timeframes'][market]
                else:
                    tf = self.plot.config['plot_timeframes']['default']

                # Plot ohlc
                ohlc = self.ohlcvs[ex][market][tf]
                self.plot.plot_ohlc(ohlc)

                # Plot orders
                orders = self.get_order_history_by_market(ex, market)
                self.plot.plot_order_annotation(orders, ohlc)

        self.plot.show()

    def get_order_history_by_market(self, ex, market):
        orders = []
        for ord in list(self.trader.order_history[ex].values()):
            if ord['market'] == market:
                orders.append(ord)
        return orders


class BacktestRunner():
    """
        Fixed test period: [(start, end), (start, end), ...]
        Randomize test: window size range, number of tests
        Fixed windows size with shift by step: window size, shift step

    """

    def __init__(self, strategy, custom_config=None):
        self.mongo = EXMongo()
        self.strategy = strategy

        _config = custom_config if custom_config is not None else config
        self._config = _config

    async def run_fixed_periods(self, periods):
        """
            Param
                periods: array, [(start, end), (start, end), ...]
        """
        reports = await self._run_all_periods(periods)
        summary = self._analyze_reports(reports)
        return summary

    async def run_random_periods(self, start, end, period_size_range, num_test):
        """ Run N tests with randomized start and period size.
            Param
                start: datetime
                end: datetime
                period_size_range: (int, int), period sizes (in days) to randomize eg. (15, 60)
                    This value should < (end - start) / 2
                num_test: int, number of tests to run
        """
        if period_size_range[0] > period_size_range[1]:
            raise ValueError("period_size_range's first number should >= the second one")

        if (end - start).days / 2 < period_size_range[1]:
            raise ValueError(f"{period_size_range[1]} days period size is too large "
                             f"for {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}, "
                             f"try size <= {int((end - start).days / 2)}")

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

        summary = await self.run_fixed_periods(periods)
        return summary

    async def run_period_with_shift_step(self, start, end, period_size, shift_step):
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

        summary = await self.run_fixed_periods(periods)
        return summary

    async def _run_all_periods(self, periods):

        rep = []
        reports = Queue(self._config['max_processes'])
        ps = queue.Queue(self._config['max_processes'])
        n_reports_left = len(periods)

        def run_backtest(backtest):
            days = (opts['end'] - opts['start']).days
            logger.info(f"Backtesting {opts['start']} / {opts['end']} ({days} days)")
            rep = backtest.run()
            reports.put({
                'period': (backtest.start, backtest.end),
                'report': rep
            })
            del backtest

        for start, end in periods:
            opts = {
                'strategy': self.strategy,
                'start': start,
                'end': end,
                'enable_plot': False
            }

            backtest = await Backtest(self.mongo).init(**opts)

            if not self._config['use_multicore']:
                if reports.full():
                    rep.append(reports.get())
                    n_reports_left -= 1

                run_backtest(backtest)

            else:
                p = Process(target=run_backtest, args=(backtest,))

                if ps.full():
                    rep.append(reports.get())
                    ps.get().join()
                    n_reports_left -= 1

                p.start()
                ps.put(p)

        # Results queued by processes must be cleared from the queue,
        # or some processes will not terminate.
        for i in range(n_reports_left):
            rep.append(reports.get())

        # Wait for all processes to terminate
        # (should be unecessary here because getting reports already blocks)
        if not self._config['use_multicore']:
            while ps.qsize() > 0:
                ps.get().join()

        return rep

    def _analyze_reports(self, reports):
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
