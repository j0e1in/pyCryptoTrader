import copy
from datetime import timedelta

from utils import config, Timer, roundup_dt, timeframe_timedelta
from trader import SimulatedTrader


class Backtest():

    def __init__(self, mongo):
        self.config = config['backtest']
        self.mongo = mongo

    async def init(self, options):
        """ Can be used to reset and run tests with different options.
            Param
                options: {
                    'strategy': a strategy object
                    'start': datetime
                    'end': datetime
                    'enable_trade_feed': bool, default is False (optional)
                                         Turn on trade feed if strategy requires it
                    'config_file': (optional) path to config file
                }
        """
        self._set_init_options(options)
        self.strategy.init(self.trader)
        await self._get_all_data()
        return self

    def reset(self):
        self.trader.reset()

    def _set_init_options(self, options):
        self.strategy = options['strategy']
        self.start = options['start']
        self.end = options['end']

        if 'enable_trade_feed' in options:
            self.enable_trade_feed = options['enable_trade_feed']
        else:
            self.enable_trade_feed = False

        if 'config_file' not in options:
            self.config = config['backtest']
            custom_config = None
        else:
            custom_config = load_config(options['config_file'])
            self.config = custom_config['backtest']

        self.timer = Timer(self.start, self.config['base_timeframe'])
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

        # Feed one day data to trader to let strategy has initial data to setup variables
        pre_feed_end = self.start + timedelta(days=1)
        self.trader.feed_data(pre_feed_end, self.ohlcvs)
        self.strategy.prefeed()

        # Feed the rest of data and tell trader to execute orders
        cur_time = self.timer.now()
        while cur_time < self.end:
            cur_time = self.timer.now()
            next_time = self.timer.next()
            self.trader.feed_data(next_time, self.ohlcvs)
            self.trader.tick() # execute orders

        for ex, markets in self.markets.items():
            self.trader.cancel_all_orders(ex)
            self.trader.close_all_positions(ex)

        self.trader.tick()  # force execution of all close position orders
        self._analyze_orders()
        return self.report

    def _init_report(self):
        return {
            "initial_fund": copy.deepcopy(self.trader.wallet),
            "initial_value": self._calc_total_value(self.timer.now()),
            "final_value": 0,
            "PL": 0,
            "PL(%)": 0,
            "margin_PLs": [],
            "#_profit_trades": 0,
            "#_loss_trades": 0,
        }

    def _analyze_orders(self):
        # Calculate total PL
        self.report['final_value'] = self._calc_total_value(self.timer.now())
        self.report['PL'] = self.report['final_value'] - self.report['initial_value']
        self.report['PL(%)'] = self.report['PL'] / self.report['initial_value']

        for ex, orders in self.trader.order_history.items():
            for _, order in orders.items():
                if order['margin']:
                    self.report['margin_PLs'].append(order['PL'])

                    # Calculate number of profit/loss trades
                    if order['PL'] >= 0:
                        self.report['#_profit_trades'] += 1
                    else:
                        self.report['#_loss_trades'] += 1

                # TODO: Add PL calculations for normal order

    def _calc_total_value(self, dt):
        # TODO: Add conversion to BTC than to USD at the price of other exchanges
        # for exchanges that don't have USD pairs.

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
                    price = ohlcv.loc[ohlcv.index == dt].close[0]
                    total_value += amount * price

        return total_value
