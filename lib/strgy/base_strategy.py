import pandas as pd
import copy

from backtest import Backtest
from utils import not_implemented

from pprint import pprint

## TODO
# Change create_empty_ohlcv_store and create_empty_trade_store
# and other related methods that access self.ohlcv and self.trades
# Then write Trader and PatternStrategy


class BaseStrategy():
    """ Available attributes:
            - trader: a Trader instance
            - markets: list of symbols to trade, a subset of symbols in utils.currencies
            - timeframes: list of timeframes, eg. ['1m', '5m', ...]
            - ohlcvs: dict of ohlcv DataFrames by symbol, eg. {
                'BTCUSD': {
                    '1m': DataFrame(...),
                    '5m': DataFrame(...),
                    ...
                }
            }
            - trades: dict of DataFrame of trades by symbol, eg. {
                'BTCUSD': [...],
                ...
            }
            - open
            - close
            - high
            - low
            - volume

    """

    def __init__(self, trader, markets, timeframes):
        self.trader = trader
        self.markets = markets
        self.timeframes = timeframes
        self.ohlcvs = self.create_empty_ohlcv_store(timeframes)
        self.trades = self.create_empty_trade_store()
        self.set_ohlcv_stores()

    def strategy(self):
        """ Perform buy/sell actions here.
            Should be implemented in a child class.
        """
        not_implemented()

    def buy(self, market, amount, margin=False):
        self.trader.close_all_positions()
        self.trader.cancel_all_orders()
        self.trader.open(market, 'buy', 'market', amount, margin)

    def sell(self, amount, margin=False):
        self.trader.close_all_positions()
        self.trader.cancel_all_orders()
        self.trader.open(market, 'sell', 'market', amount, margin)

    def run(self):
        order = self.strategy() # order can be None for doing nothing
        return order

    def feed_ohlcv(self, ohlcv, symbol, timeframe):
        if isinstance(ohlcv, dict):
            ohlcv = [ohlcv]

        oh = self.ohlcvs[symbol][timeframe]
        oh = oh.append(ohlcv)
        self.set_ohlcv_stores()

    def feed_trades(self, trades, symbol):
        if isinstance(trades, dict):
            trades = [trades]

        self.trades[symbol] = self.trades[symbol].append(trades)

    def create_empty_ohlcv_store(self, timeframes):
        cols = ['timestamp', 'open', 'close', 'high', 'low', 'volume']

        dfs = {tf: None for tf in timeframes}
        ohlcv = {}

        for tf in timeframes:
            dfs[tf] = pd.DataFrame(columns=cols)
            dfs[tf].set_index('timestamp', inplace=True)

        for market in self.markets:
            ohlcv[market] = copy.deepcopy(dfs) # TODO: check if dfs are copied

        return ohlcv

    def create_empty_trade_store(self):
        cols = ['id', 'timestamp', 'side', 'price', 'amount']

        df = pd.DataFrame(columns=cols)
        df.set_index('id', inplace=True)

        trades = {}
        for market in self.markets:
            trades[market] = copy.deepcopy(df) # TODO: check if dfs are copied

        return trades

    def set_ohlcv_stores(self):
        self.open = self.set_store('open')
        self.close = self.set_store('close')
        self.high = self.set_store('high')
        self.low = self.set_store('low')
        self.volume = self.set_store('volume')

    def set_store(self, type):
        store = {sym: {} for sym in self.markets}
        for sym in self.markets:
            for tf in self.timeframes:
                store[sym][tf] = self.ohlcvs[sym][tf][type]
        return store
