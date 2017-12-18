from strgy.base_strategy import SingleExchangeStrategy


class PatternStrategy(SingleExchangeStrategy):

    def __init__(self, ex):
        super().__init__(ex)

    def strategy(self):
        pass
        # cur_price = self.trader.cur_price()

        # if cur_price < self.base_price() * 0.95:
        #     self.open('buy', 'market', self.account['balance'] * 0.9, margin=True)
        # elif cur_price > self.base_price() * 1.30:
        #     self.open('sell', 'market', self.account['balance'] * 0.9, margin=True)

    def base_price(self):
        # if stablize for
        pass
