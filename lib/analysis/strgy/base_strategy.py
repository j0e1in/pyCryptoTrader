from utils import config


class SingleExchangeStrategy():
    """ Available attributes:
            - trader
            - ex
            - markets
            - timeframes
            - trades
        Avaiable methods:
            - buy
            - sell
            - calc_market_amount
    """

    def __init__(self, ex, custom_config=None):
        _config = custom_config if custom_config else config
        self._config = _config
        self.p = _config['analysis']['params']

        self.ex = ex
        self.fast_mode = False
        self.prefeed_days = 1 # time period for pre-feed data,
                              # default is 1, child class can set to different ones in `init_vars()`

    def set_config(self, config):
        self._config = config
        self.p = config['analysis']['params']
        self.init_vars()

    def init(self, trader):
        self.ops = []
        self.trader = trader
        self.markets = self.trader.markets[self.ex]
        self.timeframes = self.trader.timeframes[self.ex]
        self.ohlcvs = self.trader.ohlcvs[self.ex]
        self.trades = self.trader.trades[self.ex]
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

    def buy(self, market, spend, margin=False):
        """ Place an buy market order. """
        if self.fast_mode:
            raise RuntimeError("Wrong method is called in fast mode.")
        self.trade('buy', market, spend, margin)

    def sell(self, market, spend, margin=False):
        """ Place an sell market order. """
        if self.fast_mode:
            raise RuntimeError("Wrong method is called in fast mode.")
        self.trade('sell', market, spend, margin)

    def clean_orders(self, side='all'):
        """
            Param
                side: 'buy' / 'sell' / 'all'
        """
        if self.fast_mode:
            raise RuntimeError("Wrong method is called in fast mode.")
        self.trader.cancel_all_orders(self.ex)
        self.trader.close_all_positions(self.ex, side=side)

    def trade(self, side, market, spend, margin=False):
        price = self.trader.cur_price(self.ex, market, now)
        curr = self.trader.trading_currency(market, side, margin)
        value = spend * price if curr != 'USD' else spend

        if value < self.trader.config['min_order_value']:
            return

        amount = self.calc_market_amount(side, market, spend, margin)
        order = self.trader.generate_order(self.ex, market, side, 'market', amount, margin=margin)

        self.trader.open(order)

    def op_buy(self, now, market, spend, margin=False):
        if not self.fast_mode:
            raise RuntimeError("Wrong method is called in slow mode.")
        self.trade('buy', now, market, spend, margin)

    def op_sell(self, now, market, spend, margin=False):
        if not self.fast_mode:
            raise RuntimeError("Wrong method is called in slow mode.")
        self.trade('sell', now, market, spend, margin)

    def op_clean_orders(self, side, now):
        """
            Param
                side: 'buy' / 'sell' / 'all'
        """
        if not self.fast_mode:
            raise RuntimeError("Wrong method is called in slow mode.")
        self.append_op(self.trader.op_cancel_all_orders(self.ex, now))
        self.append_op(self.trader.op_close_all_positions(self.ex, now, side=side))

    def trade(self, side, now, market, spend, margin=False):
        ## TODO: Add BTC pairs value conversion or more precised min value restraint
        price = self.trader.cur_price(self.ex, market, now)
        curr = self.trader.trading_currency(market, side, margin)
        value = spend * price if curr != 'USD' else spend

        if value < self.trader.config['min_order_value']:
            return

        amount = self.calc_market_amount(side, market, spend, margin, now)
        order = self.trader.generate_order(self.ex, market, side, 'market', amount, margin=margin)

        self.append_op(self.trader.op_open(order, now))

    def calc_market_amount(self, side, market, spend, margin=False, now=None):
        price = self.trader.cur_price(self.ex, market, now)
        amount = 0
        if not margin:
            amount = spend if side == 'sell' else spend / price
        else:
            amount = spend / price * self.trader.config['margin_rate']
        return amount

    def append_op(self, op):
        if not self.fast_mode:
            raise RuntimeError("Wrong method is called in slow mode.")
        self.ops.append(op)

