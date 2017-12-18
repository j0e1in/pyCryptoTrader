from strgy.base_strategy import SingleExchangeStrategy


class PatternStrategy(SingleExchangeStrategy):

    def __init__(self, ex):
        super().__init__(ex)

    def init_vars(self):
        self.market = self.markets[0]  # trade with only first market
        self.long = False
        self.short = False
        self.base = None

    def prefeed(self):
        import pdb; pdb.set_trace()  # breakpoint ee264902 //
        self.base = self.close[self.market]['5m'].mean()


    def strategy(self):
        portion = 0.9

        cur_price = self.trader.cur_price(self.ex, self.market)
        amount = self.calc_market_amount(self.market, portion)

        if not self.long and cur_price < self.base_price() * 0.9:
            self.buy(self.market, amount, True)
            self.long = True
            self.short = False

        elif not self.short and cur_price > self.base_price() * 1.10:
            self.sell(self.market, amount, True)
            self.long = False
            self.short = True

    def base_price(self):
        pass