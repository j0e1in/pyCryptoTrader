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
        self.ops = []
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
            self.fast_strategy()
            return self.ops
        else:
            raise ValueError("Fast mode is not enabled.")

    def buy(self, market, cost, margin=False):
        """ Place an buy market order. """
        self.trade('buy', market, cost, margin)

    def sell(self, market, cost, margin=False):
        """ Place an sell market order. """
        self.trade('sell', market, cost, margin)

    def trade(self, side, market, cost, margin=False):
        self.trader.close_all_positions(self.ex)
        self.trader.cancel_all_orders(self.ex)
        amount = self.calc_market_amount(side, market, cost, margin)
        order = self.trader.generate_order(self.ex, market, side, 'market', amount, margin=margin)
        self.trader.open(order)

    def op_buy(self, now, market, cost, margin=False):
        self.trade('buy', now, market, cost, margin)

    def op_sell(self, now, market, cost, margin=False):
        self.trade('sell', now, market, cost, margin)

    def trade(self, side, now, market, cost, margin=False):
        self.append_op(self.trader.op_close_all_positions(self.ex, now))
        self.append_op(self.trader.op_cancel_all_orders(self.ex, now))
        amount = self.calc_market_amount(side, market, cost, margin, now)
        order = self.trader.generate_order(self.ex, market, side, 'market', amount, margin=margin)
        self.append_op(self.trader.op_open(order, now))

    def calc_market_amount(self, side, market, cost, margin=False, now=None):
        price = self.trader.cur_price(self.ex, market, now)
        amount = 0
        if not margin:
            amount = cost if side == 'sell' else cost / price
        else:
            amount = cost / price * self.trader.config['margin_rate']
        return amount

    def append_op(self, op):
        self.ops.append(op)

