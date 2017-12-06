import pandas as pd

from backtest import Backtest
from utils import not_implemented

from pprint import pprint

class BaseStrategy():

    def __init__(self, ohlcv_timeframes):
        self.ohlcvs = self.create_empty_ohlcv_store(ohlcv_timeframes)

    def setup(self, options):
        not_implemented()

    def _strategy(self):
        """ Strategy logic that should be implemented in a child class. """
        not_implemented()

    def feed_ohlcv(self, ohlcv, timeframe):
        if isinstance(ohlcv, dict):
            ohlcv = [ohlcv]

        self.ohlcvs[timeframe] = self.ohlcvs[timeframe].append(ohlcv)

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

    def create_empty_trade_store(self, timeframes):
        cols = ['id', 'timestamp', 'symbol', 'side', 'price', 'amount']
        df = pd.DataFrame(columns=cols)
        df.set_index('id', inplace=True)
        return df