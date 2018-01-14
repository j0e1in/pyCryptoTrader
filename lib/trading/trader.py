from datetime import timedelta
from pprint import pprint
import asyncio
import logging
import pandas as pd

from trading import exchange
from utils import config, \
                  load_keys, \
                  utc_now, \
                  rounddown_dt, \
                  roundup_dt

from ipdb import set_trace as trace

logger = logging.getLogger()


class SingleEXTrader():

    def __init__(self, mongo, ex_id, custom_config=None, verbose=False):
        self.mongo = mongo
        self.verbose = verbose
        self.loop = asyncio.get_event_loop()
        self._config = custom_config if custom_config else config
        self.config = self._config['trading']

        # Requires self attributes above, put this at last
        self.ex = self.init_exchange(ex_id)
        self.markets = self.ex.markets
        self.timeframes = self.ex.timeframes
        self.ohlcv = self.create_empty_ohlcv_store()

    def init_exchange(self, ex_id):
        key = load_keys(self._config['key_file'])[ex_id]
        ex_class = getattr(exchange, str.capitalize(ex_id))
        return ex_class(self.mongo, key['apiKey'], key['secret'],
                        custom_config=self._config,
                        verbose=self.verbose)

    def start(self):
        """ All-in-one entry for starting trading bot. """
        # Get required starting tasks of exchange.
        ex_start_tasks = self.ex.start_tasks(log=self.verbose)

        # Start routines required by exchange and trader itself
        self.loop.run_until_complete(asyncio.wait([
            *ex_start_tasks,
            self._start()
        ]))

    async def _start(self):
        """ Starting entry for OnlineTrader. """
        await self.ex_ready()
        logger.info("Exchange is ready")

        await self.start_trading()

    async def ex_ready(self):
        while True:
            if self.ex.is_ready():
                return True
            else:
                await asyncio.sleep(2)

    async def start_trading(self):
        logger.info("Start trading...")

        while True:
            await self.update_ohlcv()



    async def update_ohlcv(self):
        td = timedelta(days=self.config['strategy']['ohlcv_days'])
        end = roundup_dt(utc_now(), min=1)
        start = end - td
        self.ohlcv = await self.mongo.get_ohlcvs_of_symbols(self.ex.exname, self.markets, self.timeframes, start, end)

    def create_empty_ohlcv_store(self):
        """ ohlcv[ex][market][ft] """
        cols = ['timestamp', 'open', 'close', 'high', 'low', 'volume']
        ohlcv = {}

        df = pd.DataFrame(columns=cols)
        df.set_index('timestamp', inplace=True)

        # Each exchange has different timeframes
        for market in self.markets:
            ohlcv[market] = {}

            for tf in self.timeframes:
                ohlcv[market][tf] = df.copy(deep=True)

        return ohlcv
