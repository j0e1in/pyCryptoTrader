from utils import not_implemented


class BaseStrategy():
    """ Available attributes:
            - open
            - close
            - high
            - low
            - volume
    """

    def __init__(self, trader):
        self.trader = trader
        self.set_stores()

    def strategy(self):
        """ Perform buy/sell actions here.
            Should be implemented in a child class.
        """
        not_implemented()

    def buy(self, market, amount, margin=False):
        self.trader.close_all_positions()
        self.trader.cancel_all_orders()
        self.trader.open(market, 'buy', 'market', amount, margin)

    def sell(self, market, amount, margin=False):
        self.trader.close_all_positions()
        self.trader.cancel_all_orders()
        self.trader.open(market, 'sell', 'market', amount, margin)

    def run(self):
        self.strategy()

    def set_stores(self):
        """ Set shorthand attributes. """
        self.open = self.set_store('open')
        self.close = self.set_store('close')
        self.high = self.set_store('high')
        self.low = self.set_store('low')
        self.volume = self.set_store('volume')
        self.trades = self.trader.trades

    def set_store(self, type):
        store = {sym: {} for sym in self.trader.markets}
        for sym in self.trader.markets:
            for tf in self.trader.timeframes:
                store[sym][tf] = self.trader.ohlcvs[sym][tf][type]
        return store
