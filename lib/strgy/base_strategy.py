from utils import not_implemented


class SingleExchangeStrategy():
    """ Available attributes:
            - trader
            - ex
            - markets
            - timeframes
            - open
            - close
            - high
            - low
            - volume
            - trades
        Avaiable methods:
            - buy
            - sell
            - calc_market_amount
    """

    def __init__(self, ex):
        self.ex = ex
        self.fast_mode = False

    def init(self, trader):
        self.trader = trader
        self.markets = self.trader.markets[self.ex]
        self.timeframes = self.trader.timeframes[self.ex]
        self.ohlcvs = self.trader.ohlcvs[self.ex]
        self.trades = self.trader.trades[self.ex]
        self.prefeed_days = 1 # time period for pre-feed data,
                              # default is 1, child class can set to different ones in `init_vars()`
        self.init_vars()
        return self

    def init_vars(self):
        """ (Optional)
            Implemented by user.
            Child class implement this method.
        """
        pass

    def prefeed(self):
        """ (Optional)
            Implemented by user.
            Read pre-feed data from trader to setup initial variables.
        """
        pass

    def strategy(self):
        """ Implemented by user.
            Perform buy/sell actions here.
            Should be implemented in a child class.
        """
        pass

    def run(self):
        if not self.fast_mode:
            self.strategy()
        else:
            raise ValueError("Fast mode is enabled.")

    def fast_strategy(self):
        """ Implemented by user.
            Returns a list of `(datetime, order)`, to let trader perform the orders.
            Should be implemented in a child class.
        """
        pass

    def fast_run(self):
        if self.fast_mode:
            return self.fast_strategy()
        else:
            raise ValueError("Fast mode is not enabled.")

    def buy(self, market, amount, margin=False):
        self.trader.close_all_positions()
        self.trader.cancel_all_orders()
        order = self.trader.generate_order(self.ex, market, 'buy', 'market', amount, margin=margin)
        self.trader.open(order)

    def sell(self, market, amount, margin=False):
        self.trader.close_all_positions()
        self.trader.cancel_all_orders()
        order = self.trader.generate_order(self.ex, market, 'sell', 'market', amount, margin=margin)
        self.trader.open(order)

    def calc_market_amount(market, portion, margin=False):
        """ Calculate qoute balance (eg. USD, BTC) amount for market orders. """
        price = self.trader.cur_price(self.ex, market)
        curr = market.split('/')[1]
        amount = self.trader.wallet[self.ex][curr] * portion / price
        if margin:
            amount *= self.trader.config['margin_rate']
        return amount
