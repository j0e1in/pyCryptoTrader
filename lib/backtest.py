import copy
from datetime import timedelta

from utils import config, Timer, roundup_dt, timeframe_timedelta
from trader import SimulatedTrader, FastTrader
from plot import Plot


class Backtest():

    def __init__(self, mongo):
        self.config = config['backtest']
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
        self.strategy = options['strategy']
        self.start = options['start']
        self.end = options['end']

        if 'enable_trade_feed' in options:
            self.enable_trade_feed = options['enable_trade_feed']
        else:
            self.enable_trade_feed = False

        # Set backtest config file
        if 'custom_config' not in options:
            custom_config = None
            self.config = config['backtest']
            self.plot = Plot()
        else:
            custom_config = options['custom_config']
            self.config = custom_config['backtest']
            self.plot = Plot(custom_config=custom_config)

        self.timer = Timer(self.start, self.config['base_timeframe'])

        if self.config['fast_mode']:
            self.trader = FastTrader(self.timer, self.strategy, custom_config)
            self.trader.fast_mode = True
            self.strategy.fast_mode = True
        else:
            self.trader = SimulatedTrader(self.timer, self.strategy, custom_config)

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

        if self.plot.config['enable']:
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
            self.trader.tick() # execute orders

        self.trader.liquidate()

    def _init_report(self):
        return {
            "initial_fund": copy.deepcopy(self.trader.wallet),
            "initial_value": self._calc_total_value(self.timer.now()),
            "final_fund": None,
            "final_value": 0,
            "PL": 0,
            "PL(%)": 0,
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

    def get_order_history_by_market(self, ex, market):
        orders = []
        for ord in list(self.trader.order_history[ex].values()):
            if ord['market'] == market:
                orders.append(ord)
        return orders








