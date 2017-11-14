from backtest import Backtest
from utils import not_implemented

class BaseStrategy(Backtest):

    def __init__(self, mongo):
        super().__init__(mongo)

    async def setup(self, options):
        options['strategy'] = self._strategy
        await super().setup(options)

    def _strategy(self):
        """ Actual strategy logic that should be implemented in a child class. """
        not_implemented()
