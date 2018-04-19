import copy
import logging
import numpy as np

from db import Datastore
from trading.strategy import SingleEXStrategy
from trading.indicators import Indicator
from utils import \
    rounddown_dt, \
    roundup_dt, \
    is_within, \
    tf_td, \
    utc_now, \
    config, \
    MIN_DT

logger = logging.getLogger('pyct.debug_execute')
logger.setLevel(logging.DEBUG)

NONE = 'NONE'
BUY = 'BUY'
SELL = 'SELL'
CLOSE = 'CLOSE'
CANCEL = 'CANCEL'

class PatternStrategy(SingleEXStrategy):

    ds_list = [
        'last_sig_exec'
    ]

    def __init__(self, trader, custom_config=None):
        super().__init__(trader, custom_config)
        self.ind = Indicator(custom_config=self._config)
        self.ds = Datastore.create(f"{self.trader.uid}:strategy")
        self.last_sig_exec = self.ds.get('last_sig_exec', {})
        self.signals = None

        if not self.last_sig_exec:
            for market in trader.ex.markets:
                self.last_sig_exec[market] = {
                    'action': NONE,
                    'time': MIN_DT,
                }

        self.ds.last_sig_exec = self.last_sig_exec

    def init_vars(self):
        """ Variables declared here are reset everytime when ohlcv is updated. """
        pass

    async def strategy(self):
        signals = {}
        params = self.trader.mongo.get_params()
        from ipdb import set_trace; set_trace()
        for market in self.trader.ex.markets:
            if market not in params:
                logger.warning(f"No param for market {market}, using common param")
                param = params['common']
            else:
                param = params[market]

            signals[market] = self.calc_signal(market, param)

        self.signals = signals
        await self.execute(signals)
        return signals

    async def execute(self, signals):
        async def exec_sig(sig, market, use_prev_sig):
            action = await self.execute_sig(sig, market, use_prev_sig=use_prev_sig)

            if action != NONE:
                self.last_sig_exec[market]['time'] = sig.index[-1]
                self.last_sig_exec[market]['action'] = action

            self.ds.last_sig_exec = self.last_sig_exec
            return action

        tftd = tf_td(self.trader.config['indicator_tf'])
        market_ranks = self.rank_markets()
        actions = {market: NONE for market in market_ranks}

        for market in market_ranks:
            sig = signals[market]

            # Ensure ohlcv is up-to-date
            if is_within(sig.index[-1], tftd):

                if near_start(sig.index[-1], tftd):
                    logger.debug("near_start")

                    if not executed(sig, self.last_sig_exec, market, tftd):
                        logger.debug(f"executing signal")
                        actions[market] = await exec_sig(sig, market, use_prev_sig=True)

        return actions

    async def execute_sig(self, sig, market, use_prev_sig=False):
        action = NONE
        orders = []
        conf = sig[-1] if not use_prev_sig else sig[-2]

        logger = logging.getLogger('pyct')

        if conf > 0:
            logger.debug(f"Create {market} buy order")
            logger.debug(f"{market} indicator signal @ {utc_now()}\n{sig[-5:]}")
            action = BUY
            orders = await self.trader.long(market, conf, type='limit')

        elif conf < 0:
            logger.debug(f"Create {market} sell order")
            logger.debug(f"{market} indicator signal @ {utc_now()}\n{sig[-5:]}")
            action = SELL
            orders = await self.trader.short(market, conf, type='limit')

        elif conf == 0:
            logger.debug(f"Close {market} positions")
            logger.debug(f"{market} indicator signal @ {utc_now()}\n{sig[-5:]}")
            action = CLOSE
            orders = await self.trader.close_position(market, conf, type='limit')

        if orders:
            await self.trader.notifier.notify_open_orders_succ(orders)

        return action

    def calc_signal(self, market, param):
        """ Main algorithm which calculates signals.
            Returns {signal, timeframe}
        """
        # Change to the param of the market
        self.ind.p = param

        ohlcv = self.trader.ohlcvs[market][self.trader.config['indicator_tf']]
        sig = self.ind.stoch_rsi_sig(ohlcv)

        return sig

    def rank_markets(self):
        """ Rank markets' profitability.
            Returns a list of markets.
        """
        # Current method: hard coded market rank base on backtest profitibitlity
        backtest_profit_rank = [
            "XRP/USD",
            "BCH/USD",
            "BTC/USD",
            "ETH/USD",
        ]

        trade_markets = copy.deepcopy(self.trader.ex.markets)
        rank = []

        for market in backtest_profit_rank:
            if market in trade_markets:
                rank.append(market)

        trade_markets = [market for market in trade_markets if market not in rank]
        rank += trade_markets
        return rank


def near_start(dt, td):
    """ Determine if dt is at the start of an interval """
    ratio = config['trading']['strategy']['near_start_ratio']
    rdt = rounddown_dt(dt, td)
    return True if (dt - rdt) <= td * ratio else False


def near_end(dt, td):
    """ Determine if dt is at the end of an interval """
    ratio = config['trading']['strategy']['near_end_ratio']
    rdt = roundup_dt(dt, td)
    return True if (rdt - dt) <= td * ratio else False


def executed(sig, last_sig_exec, market, tftd):
    """ Determine if last sig execution is at the latest 'near_end' period """
    action = last_sig_exec[market]['action']
    time = last_sig_exec[market]['time']

    if near_start(sig.index[-1], tftd):

        if near_start(time, tftd) \
        and time < roundup_dt(sig.index[-1], tftd) \
        and time >= rounddown_dt(sig.index[-1], tftd) \
        and action == to_action(sig.iloc[-2]):
            logger.debug(f'Executed, time: {time}')
            return True

        else:
            logger.debug(f'Not Executed, time: {time}')
            return False

    raise RuntimeError("Should only call this function if near_start or near_end")


def changed(sig, last_sig_exec, market, tftd):
    """ Determine if latest signal has changed """
    if not executed(sig, last_sig_exec, market, tftd):
        logger.warning(f"executed is False")
        return False

    last_action = last_sig_exec[market]['action']

    if near_end(sig.index[-1], tftd):
        if last_action != to_action(sig.iloc[-1]):
            logger.debug('Changed')
            return True
        else:
            logger.debug('Not Changed')
            return False

    elif near_start(sig.index[-1], tftd):
        if last_action != to_action(sig.iloc[-2]):
            logger.debug('Changed')
            return True
        else:
            logger.debug('Not Changed')
            return False

    raise RuntimeError("Should only call this function if near_start or near_end")


def to_action(conf):
    if np.isnan(conf):
        return NONE
    elif conf is 0:
        return CLOSE
    elif conf > 0:
        return BUY
    elif conf < 0:
        return SELL
