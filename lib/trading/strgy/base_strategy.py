from utils import config, not_implemented


class SingleEXStrategy():

    def __init__(self, trader, custom_config=None):
        self.trader = trader

        self._config = custom_config if custom_config else config
        self.p = self.trader.config['params']

    def refresh(self):
        self.init_vars()

    def run(self):
        self.refresh()
        self.strategy()

    def strategy(self):
        not_implemented()

    def init_vars(self):
        # This function is optional for child classes
        pass