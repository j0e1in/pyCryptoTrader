import pandas as pd

from backtest import Backtest
from utils import not_implemented

from pprint import pprint


class BaseStrategy():

    def __init__(self, trader, ohlcv_timeframes):
        self.trader = trader
        self.timeframes = ohlcv_timeframes
        self.ohlcvs = self.create_empty_ohlcv_store(ohlcv_timeframes)
        self.trades = self.create_empty_trade_store()
        self.set_ohlcv_store()

    def setup(self, options):
        not_implemented()

    def strategy(self):
        """ Perform buy/sell actions here.
            Should be implemented in a child class.
        """
        not_implemented()

    def buy(self, amount, margin=False):
        pass

    def sell(self, amount, margin=False):
        pass

    def run(self):
        order = self.strategy() # order can be None for doing nothing
        return order

    def feed_ohlcv(self, ohlcv, timeframe):
        if isinstance(ohlcv, dict):
            ohlcv = [ohlcv]

        self.ohlcvs[timeframe] = self.ohlcvs[timeframe].append(ohlcv)
        self.set_ohlcv_store()

    def feed_trades(self, trades):
        if isinstance(trades, dict):
            trades = [trades]

        self.trades = self.trades.append(trades)

    def create_empty_ohlcv_store(self, timeframes):
        cols = ['timestamp', 'open', 'close', 'high', 'low', 'volume']
        dfs = {tf: None for tf in timeframes}

        for tf in timeframes:
            dfs[tf] = pd.DataFrame(columns=cols)
            dfs[tf].set_index('timestamp', inplace=True)

        return dfs

    def create_empty_trade_store(self):
        cols = ['id', 'timestamp', 'side', 'price', 'amount']
        df = pd.DataFrame(columns=cols)
        df.set_index('id', inplace=True)
        return df

    def set_ohlcv_store(self):
        self.open = self.set_store('open')
        self.close = self.set_store('close')
        self.high = self.set_store('high')
        self.low = self.set_store('low')
        self.volume = self.set_store('volume')

    def set_store(self, type):
        store = {}
        for tf in self.timeframes:
            store[tf] = self.ohlcvs[tf][type]
        return store
