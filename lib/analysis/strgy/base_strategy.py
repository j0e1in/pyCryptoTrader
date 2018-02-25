from datetime import timedelta

import copy
import logging

from utils import config

logger = logging.getLogger()


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

    def set_config(self, cfg):
        self._config = cfg
        self.p = cfg['analysis']['params']
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

    def buy(self, market, spend, margin=False, stop_loss=None, stop_profit=None):
        """ Place an buy market order. """
        if self.fast_mode:
            raise RuntimeError("Wrong method is called in fast mode.")
        self.trade('buy', market, spend, margin, stop_loss, stop_profit)

    def sell(self, market, spend, margin=False, stop_loss=None, stop_profit=None):
        """ Place an sell market order. """
        if self.fast_mode:
            raise RuntimeError("Wrong method is called in fast mode.")
        self.trade('sell', market, spend, margin, stop_loss, stop_profit)

    def clean_orders(self, side='all'):
        """
            Param
                side: 'buy' / 'sell' / 'all'
        """
        if self.fast_mode:
            raise RuntimeError("Wrong method is called in fast mode.")
        self.trader.cancel_all_orders(self.ex)
        self.trader.close_all_positions(self.ex, side=side)

    def trade(self, side, market, spend, margin=False, stop_loss=None, stop_profit=None):
        price = self.trader.cur_price(self.ex, market)
        curr = self.trader.trading_currency(market, side, margin)
        value = spend * price if curr != 'USD' else spend

        if value < self.trader.config['min_order_value']:
            return

        amount = self.calc_market_amount(side, market, spend, margin)
        order = self.trader.generate_order(self.ex, market, side, 'market', amount,
                                           margin=margin,
                                           stop_loss=stop_loss,
                                           stop_profit=stop_profit)

        self.trader.open(order)

    def op_buy(self, now, market, spend, margin=False, stop_loss=None, stop_profit=None):
        if not self.fast_mode:
            raise RuntimeError("Wrong method is called in slow mode.")
        self.op_trade('buy', now, market, spend, margin, stop_loss, stop_profit)

    def op_sell(self, now, market, spend, margin=False, stop_loss=None, stop_profit=None):
        if not self.fast_mode:
            raise RuntimeError("Wrong method is called in slow mode.")
        self.op_trade('sell', now, market, spend, margin, stop_loss, stop_profit)

    def op_clean_orders(self, side, now):
        """
            Param
                side: 'buy' / 'sell' / 'all'
        """
        if not self.fast_mode:
            raise RuntimeError("Wrong method is called in slow mode.")
        self.append_op(self.trader.op_cancel_all_orders(self.ex, now))
        self.append_op(self.trader.op_close_all_positions(self.ex, now, side=side))

    def op_trade(self, side, now, market, spend, margin=False, stop_loss=None, stop_profit=None):
        ## TODO: Add BTC pairs value conversion or more precised min value restraint
        price = self.trader.cur_price(self.ex, market, now)
        curr = self.trader.trading_currency(market, side, margin)
        value = spend * price if curr != 'USD' else spend

        if value < self.trader.config['min_order_value']:
            return

        amount = self.calc_market_amount(side, market, spend, margin, now)
        order = self.trader.generate_order(self.ex, market, side, 'market', amount,
                                           margin=margin,
                                           stop_loss=stop_loss,
                                           stop_profit=stop_profit)

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

    def op_execute_position_stop(self, end):
        """" Execute stop loss or stop profit(trailing stop), if matches. """

        op_positions = copy.deepcopy(self.trader.op_positions)
        for _, positions in op_positions.items():
            for _, pos in positions.items():


                start = pos['op_open_time'] + timedelta(seconds=1)
                ohlcv = self.trader.ohlcvs[self.ex][pos['market']][self.trader.config['indicator_tf']][start:end]
                if start == end:
                    logger.warn('start == end')

                if len(ohlcv) > 0:

                    if pos['stop_loss']:
                        stop_loss = ()
                        target_low  = pos['op_open_price'] * (1 - pos['stop_loss']) # for buy
                        target_high = pos['op_open_price'] * (1 + pos['stop_loss']) # for sell

                        # Check buy stop loss
                        if pos['side'] == 'buy' \
                        and ohlcv.low.min() <= target_low:
                            bar = ohlcv[ohlcv.low <= target_low].iloc[0]
                            stop_loss = (bar.name, target_low)

                        # Check sell stop loss
                        elif pos['side'] == 'sell' \
                        and ohlcv.high.max() >= target_high:
                            bar = ohlcv[ohlcv.high >= target_high].iloc[0]
                            stop_loss = (bar.name, target_high)

                        if stop_loss:
                            pos['op_close_time'] = stop_loss[0]
                            pos['op_close_price'] = stop_loss[1]
                            self.append_op(self.trader.op_close_position(pos, pos['op_close_time']))

                            if self._config['mode'] == 'debug':
                                logger.debug(f"Stop {pos['side']} loss @ {pos['op_close_price']:.3f} ({pos['op_close_time']})")

                            continue

                    if pos['stop_profit']: # If stop_loss is not applied, check stop profit
                        stop_profit = ()

                        if pos['side'] == 'buy':
                            diff_low = pos['op_open_price'] * pos['stop_profit']

                            for dt, oh in ohlcv.iterrows():
                                cur_high = ohlcv[:dt + timedelta(seconds=1)].high.max()
                                target_low = cur_high - diff_low

                                if target_low > pos['op_open_price'] and oh.low < target_low:
                                    # if stop_profit is not set
                                    # if the close datetime (dt) is earlier, use that dt
                                    if not stop_profit \
                                    or (stop_profit and stop_profit[0] > dt):
                                        stop_profit = (dt, target_low)

                        elif pos['side'] == 'sell':
                            diff_high = pos['op_open_price'] * pos['stop_profit']

                            for dt, oh in ohlcv.iterrows():
                                cur_low = ohlcv[:dt + timedelta(seconds=1)].low.min()
                                target_high = cur_low + diff_high

                                if target_high < pos['op_open_price'] and oh.high > target_high:
                                    # if stop_profit is not set
                                    # if the close datetime (dt) is earlier, use that dt
                                    if not stop_profit \
                                    or (stop_profit and stop_profit[0] > dt):
                                        stop_profit = (dt, target_high)

                        if stop_profit:
                            pos['op_close_time'] = stop_profit[0]
                            pos['op_close_price'] = stop_profit[1]
                            self.append_op(self.trader.op_close_position(pos, pos['op_close_time']))

                            if self._config['mode'] == 'debug':
                                logger.debug(f"Stop {pos['side']} profit @ {pos['op_close_price']:.3f} ({pos['op_close_time']})")



