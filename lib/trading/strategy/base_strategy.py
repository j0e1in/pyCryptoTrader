from utils import config, not_implemented


class SingleEXStrategy():

    def __init__(self, trader, custom_config=None):
        self.trader = trader

        self._config = custom_config or config
        self.p = self.trader.config['params']['common']

    def refresh(self):
        self.init_vars()

    async def run(self):
        self.refresh()
        return await self.strategy()

    def strategy(self):
        not_implemented()

    def init_vars(self):
        # This function is optional for child classes
        pass