from utils import not_implemented


class SingleExchangeStrategy():
    """ Available attributes:
            - open
            - close
            - high
            - low
            - volume
    """

    def __init__(self, ex):
        self.ex = ex

    def init(self, trader):
        self.trader = trader
        self.markets = self.trader.markets[self.ex]
        self.timeframes = self.trader.timeframes[self.ex]
        self.set_stores()
        return self

    def strategy(self):
        """ Perform buy/sell actions here.
            Should be implemented in a child class.
        """
        not_implemented()

    def run(self):
        self.strategy()

    def long(self, market, amount, margin=False):
        self.trader.close_all_positions()
        self.trader.cancel_all_orders()
        order = self.trader.generate_order(self.ex, market, 'buy', 'market', amount, margin=margin)
        self.trader.open(order)

    def short(self, market, amount, margin=False):
        self.trader.close_all_positions()
        self.trader.cancel_all_orders()
        order = self.trader.generate_order(self.ex, market, 'sell', 'market', amount, margin=margin)
        self.trader.open(order)

    def calc_market_amount(market, portion):
        """ Calculate amount for market orders. """
        price = self.trader.cur_price(self.ex, market)
        curr = market.split('/')[1]
        amount = self.trader.wallet[self.ex][curr] * portion / price
        return amount

    def set_stores(self):
        """ Link to trader's data. """
        if self.ex not in self.trader.ohlcvs\
        or self.ex not in self.trader.trades:
            raise ValueError(f"Trader doesn't have data for required exchange: {self.ex}")

        self.open = {}
        self.close = {}
        self.high = {}
        self.low = {}
        self.volume = {}
        self.trades = {}

        for market, tfs in self.trader.ohlcvs[self.ex].items():
            self.open[market] = {}
            self.close[market] = {}
            self.high[market] = {}
            self.low[market] = {}
            self.volume[market] = {}
            for tf, ohlcv in tfs.items():
                self.open[market][tf] = ohlcv.open
                self.close[market][tf] = ohlcv.close
                self.high[market][tf] = ohlcv.high
                self.low[market][tf] = ohlcv.low
                self.volume[market][tf] = ohlcv.volume

        for market, trades in self.trader.trades[self.ex].items():
            self.trades[market] = trades


