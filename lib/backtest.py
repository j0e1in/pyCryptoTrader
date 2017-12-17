import copy

from utils import config, Timer, roundup_dt, timeframe_timedelta
from trader import SimulatedTrader


class Backtest():

    def __init__(self, mongo):
        self.config = config['backtest']
        self.mongo = mongo

    async def init(self, options={}):
        """
            Param
                options: {
                    'start': datetime
                    'end': datetime
                    'config_file': (optional) path to config file
                }
        """
        self._set_init_options(options)

        self.timer = Timer(self.start, self.config['base_timeframe'])
        self.trader = SimulatedTrader(self.timer)
        self.markets = self.trader.markets
        self.timeframes = self.trader.timeframes

        await self._get_all_data()

    def reset(self):
        self.trader.reset()

    def _set_init_options(self, options):
        if 'config_file' not in options:
            self.config = config['backtest']

        self.start = options['start']
        self.end = options['end']

    async def _get_all_data(self):
        self.ohlcvs = {}
        self.trades = {}
        for ex, markets in self.markets.items():
            self.ohlcvs[ex] = await self.mongo.get_ohlcvs_of_symbols(ex, markets, self.timeframes[ex], self.start, self.end)
            self.trades[ex] = await self.mongo.get_trades_of_symbols(ex, markets, self.start, self.end)

    def run(self):
        self.report = self._init_report()

        cur_time = self.timer.now()
        while cur_time < self.end:
            cur_time = self.timer.now()
            next_time = self.timer.next()
            self.trader.feed_data(self.ohlcvs, self.trades, cur_time, next_time)

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
