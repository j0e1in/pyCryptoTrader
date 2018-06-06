from asyncio import ensure_future
import asyncio
import ccxt.async as ccxt
import copy
import logging

from trading.exchanges import EXBase
from utils import \
    ms_dt, \
    dt_ms, \
    not_implemented, \
    execute_mongo_ops, \
    sec_ms, \
    utc_now, \
    handle_ccxt_request, \
    true_symbol

logger = logging.getLogger('pyct')


class Bitfinex(EXBase):

    ## ccxt.bitfinex APIs
    ## bitfinex / bitfinex2 methods
    # fetch_balance (O)
    # fetch_order_book (O)
    # fetch_tickers (O)
    # fetch_ticker (O)
    # fetch_trades
    # fetch_ohlcv (O)

    ## bitfinex methods
    # fetch_markets (O)
    # fetch_order (O)
    # fetch_open_orders (O)
    # fetch_my_trades (O)
    # fetch_closed_orders (O)
    # fetch_deposit_address (O)
    # create_deposit_address (O)
    # create_order (O)
    # cancel_order (O)
    # withdraw

    def __init__(self, mongo, *args, **kwargs):
        super().__init__(mongo, 'bitfinex', *args, **kwargs)

    def init_wallet(self):
        tmp = {'exchange': 0, 'margin': 0, 'funding': 0}

        wallet = {}
        wallet['USD'] = copy.deepcopy(tmp)

        for market in self._config['trading'][self.exname]['markets']:
            wallet[market.split('/')[0]] = copy.deepcopy(tmp)

        return wallet

    async def update_wallet(self):
        """
            bitfinex response:
                type: exchange / trading (margin) / deposit (funding)
        """
        self._check_auth()

        res = await handle_ccxt_request(self.ex.fetch_balance)
        for curr in res['info']:
            sym = str.upper(curr['currency'])

            if sym not in self.wallet:
                self.wallet[sym] = {'exchange': 0, 'margin': 0, 'funding': 0}

            if curr['type'] == 'exchange':
                self.wallet[sym]['exchange'] = float(curr['available'])
            elif curr['type'] == 'trading':
                self.wallet[sym]['margin'] = float(curr['available'])
            elif curr['type'] == 'deposit':
                self.wallet[sym]['funding'] = float(curr['available'])
            else:
                self.wallet[sym][curr['type']] = float(curr['available'])

        self.ready['wallet'] = True
        return self.wallet

    def get_balance(self, curr, type):
        """ Child classes should override this method to adapt to its wallet structure.
            Default has no type.
            Params
                curr: str, eg. 'USD', 'BTC', ...
                type: str, eg. 'exchange', 'margin', 'funding' etc.
        """
        if type == 'exchange':
            return self.wallet[curr]['exchange']
        elif type == 'margin':
            return self.wallet[curr]['margin']
        elif type == 'funding':
            return self.wallet[curr]['funding']
        else:
            raise ValueError(f"Wallet type {type} is not supported.")

    async def get_orderbook(self, symbol):
        params = {
            'limit_bids': self.config['orderbook_size'],
            'limit_asks': self.config['orderbook_size'],
            'group': 1, # 0 / 1
        }
        symbol = true_symbol(self.ex, symbol)
        return await super().get_orderbook(symbol, params=params)

    async def update_markets(self, once=False):
        """ Fetch same data as self.ex.load_markets
            ccxt response:
            [{'active': True,
              'base': 'BTC',
              'baseId': 'BTC',
              'id': 'BTCUSD',
              'info': {'expiration': 'NA',
                       'initial_margin': '30.0',
                       'maximum_order_size': '2000.0',
                       'minimum_margin': '15.0',
                       'minimum_order_size': '0.002',
                       'pair': 'btcusd',
                       'price_precision': 5},
              'limits': {'amount': {'max': 2000.0, 'min': 0.002},
                         'cost': {'max': None, 'min': None},
                         'price': {'max': 100000.0, 'min': 1e-05}},
              'maker': 0.001,
              'percentage': True,
              'precision': {'amount': 5, 'price': 5},
              'quote': 'USD',
              'quoteId': 'USD',
              'symbol': 'BTC/USD',
              'taker': 0.002,
              'tierBased': True,
              'tiers': {'maker': [[0, 0.001],
                                  [500000, 0.0008],
                                  [1000000, 0.0006],
                                  [2500000, 0.0004],
                                  [5000000, 0.0002],
                                  [7500000, 0],
                                  [10000000, 0],
                                  [15000000, 0],
                                  [20000000, 0],
                                  [25000000, 0],
                                  [30000000, 0]],
                        'taker': [[0, 0.002],
                                  [500000, 0.002],
                                  [1000000, 0.002],
                                  [2500000, 0.002],
                                  [5000000, 0.002],
                                  [7500000, 0.002],
                                  [10000000, 0.0018],
                                  [15000000, 0.0016],
                                  [20000000, 0.0014000000000000002],
                                  [25000000, 0.0012],
                                  [30000000, 0.001]]}}
                ...
            ]
        """
        if once: # Fetch only once
            res = await handle_ccxt_request(self.ex.fetch_markets)
            for market in res:
                if market['symbol'] in self.markets:
                    self.markets_info[market['symbol']] = market

            return self.markets_info

        logger.info(f"Start updating markets info")
        while True:
            if self.log:
                logger.info("Update markets info")

            res = await handle_ccxt_request(self.ex.fetch_markets)
            for market in res:
                if market['symbol'] in self.markets:
                    self.markets_info[market['symbol']] = market

            self.ready['markets'] = True
            await asyncio.sleep(self.config['markets_info_delay'])

    async def fetch_open_orders(self, symbol=None):
        """
            ccxt response:
            [{'amount': 0.002,
              'average': 0.0,
              'datetime': '2018-01-13T03:36:39.000Z',
              'fee': None,
              'filled': 0.0,
              'id': '7125075906',
              'price': 19999.0,
              'remaining': 0.002,
              'side': 'sell',
              'status': 'open', (open / closed / canceled)
              'symbol': 'BTC/USD',
              'timestamp': 1515814599000,
              'type': 'limit',
              'info': {'avg_execution_price': '0.0',
                       'cid': 12999037301,
                       'cid_date': '2018-01-13',
                       'exchange': None,
                       'executed_amount': '0.0',
                       'gid': None,
                       'id': 7125075906,
                       'is_cancelled': False,
                       'is_hidden': False,
                       'is_live': True,
                       'oco_order': None,
                       'original_amount': '0.002',
                       'price': '19999.0',
                       'remaining_amount': '0.002',
                       'side': 'sell',
                       'src': 'web',
                       'symbol': 'btcusd',
                       'timestamp': '1515814599.0',
                       'type': 'exchange limit',
                       'was_forced': False}}
              ...]

            Return:
            [{'amount': 0.002,
             'average': 0.0,
             'datetime': datetime.datetime(2018, 3, 12, 19, 24, 3),
             'fee': None,
             'filled': 0.0,
             'id': '9278143508',
             'margin': True,
             'price': 100.0,
             'remaining': 0.002,
             'side': 'buy',
             'status': 'open',
             'symbol': 'BTC/USD',
             'timestamp': 1520882643000,
             'type': 'limit'}]
        """
        self._check_auth()

        res = await handle_ccxt_request(self.ex.fetch_open_orders, symbol)

        orders = []
        for ord in res:
            ord = self.parse_order(ord)
            orders.append(ord)

        return orders

    async def fetch_order(self, id, parse=True):
        """ Fetch a single order using order known id.
            Param
                id: str, id of an order
                parse: bool, if False, original ccxt response will be returned directly
        """
        self._check_auth()
        ord = await handle_ccxt_request(self.ex.fetch_order, id)
        return self.parse_order(ord) if parse is True else ord

    async def fetch_positions(self, symbol=None):
        """ Fetch all open positions. Specify symbol to filter result.
            ccxt response:
            [{'amount': '0.002',
              'base': '13219.0',
              'id': 134256839,
              'pl': '-0.076828',
              'status': 'ACTIVE',
              'swap': '0.0',
              'symbol': 'btcusd',
              'timestamp': '1515947276.0'}]

            Return:
            [{'amount': '0.002',
              'base_price': '13219.0',
              'id': 134256839,
              'pl': '-0.076828',
              'status': 'ACTIVE',
              'symbol': 'BTC/USD',
              'timestamp': '1515947276.0'}]
        """
        def parse_position(pos):
            pos['amount'] = float(pos['amount'])
            pos['base_price'] = float(pos['base'])
            pos['pl'] = float(pos['pl'])
            pos['symbol'] = self.to_ccxt_symbol(pos['symbol'])
            pos['timestamp'] = sec_ms(pos['timestamp'])
            pos['datetime'] = ms_dt(pos['timestamp'])

            pos.pop('base', None)
            pos.pop('swap', None)
            return pos

        self._check_auth()
        res = await handle_ccxt_request(self.ex.private_post_positions)

        positions = []
        for pos in res:
            pos = parse_position(pos)

            if not symbol:
                positions.append(pos)
            elif pos['symbol'] == symbol:
                positions.append(pos)

        return positions

    async def fetch_my_recent_trades(self, symbol, start=None, end=None, limit=1000):
        """ Fetch most recent N trades.
            ccxt response:
            [{'amount': 0.52,
             'cost': 5038.8,
             'datetime': '2017-11-30T12:29:51.000Z',
             'fee': None,
             'id': '104858401',
             'info': {'amount': '0.52',
                      'fee_amount': '-10.0776',
                      'fee_currency': 'USD',
                      'order_id': 5607111792,
                      'price': '9690.0',
                      'tid': 104858401,
                      'timestamp': '1512044991.0',
                      'type': 'Buy'},
             'order': '5607111792',
             'price': 9690.0,
             'side': 'buy',
             'symbol': 'BTC/USD',
             'timestamp': 1512044991000,
             'type': None}]

            Return:
            [{'amount': 0.52,
             'cost': 5038.8,
             'datetime': datetime.datetime(2017, 11, 30, 12, 29, 51)
             'fee': '-10.0776',
             'fee_currency': 'USD',
             'id': '104858401',
             'order': '5607111792',
             'price': 9690.0,
             'side': 'buy',
             'symbol': 'BTC/USD',
             'timestamp': 1512044991000,
             'type': None}]
        """
        if not hasattr(self.ex, 'fetch_my_trades'):
            logger.warning(f"{self.exname} doesn't have fetch_my_trades method.")
            return []

        self._check_auth()
        symbol = true_symbol(self.ex, symbol)

        if self.log:
            logger.info(f"Fetching my {symbol} trades from {start} to {end}")

        start = dt_ms(start) if start else None
        end = dt_ms(end) if end else None

        params = {}
        if end:
            params['until'] = end

        res = await handle_ccxt_request(self.ex.fetch_my_trades, symbol, start, limit, params)
        trades = []
        for trade in res:
            self.parse_my_trade(trade)
            trades.append(trade)

        trades = trades[::-1] # reverse the order to oldest first
        return trades

    @staticmethod
    def parse_my_trade(trade):
        trade['fee'] = abs(float(trade['info']['fee_amount']))
        trade['fee_currency'] = trade['info']['fee_currency']
        trade['datetime'] = ms_dt(trade['timestamp'])
        trade.pop('info', None)
        return trade

    async def get_deposit_address(self, currency, type='exchange'):
        """
            Param:
                currency: str, eg. 'USD', 'BTC', ... (only few are supported)
                type: str, 'exchange' / 'margin' / 'funding'
                [Doc] https://docs.bitfinex.com/v1/reference#rest-auth-deposit
        """
        self._check_auth()

        if type == 'exchange':
            address_type = 'exchange'
        elif type == 'margin':
            address_type = 'trading'
        elif type == 'funding':
            address_type = 'deposit'
        else:
            raise ValueError(f"Unsupported address type: {type}")

        params = {
            'wallet_name': address_type
        }

        res = await handle_ccxt_request(self.ex.fetch_deposit_address, currency, params)

        if res['info']['result'] == 'error':
            logger.error(f"Failed to get {currency} {type} deposit address")

        return res['address']

    async def get_new_deposit_address(self, currency, type='exchange'):
        """ Generate a new address despite an old one is already existed. """
        self._check_auth()

        if type == 'exchange':
            address_type = 'exchange'
        elif type == 'margin':
            address_type = 'trading'
        elif type == 'funding':
            address_type = 'deposit'
        else:
            raise ValueError(f"Unsupported address type: {type}")

        params = {
            'wallet_name': address_type
        }

        res = await handle_ccxt_request(self.ex.create_deposit_address, currency, params)

        if res['info']['result'] == 'error':
            logger.error(f"Failed to generate {currency} {type} deposit address")

        return res['address']

    async def create_order(self, symbol, type, side, amount, *, price=None, params={}):
        """
            Params
                symbol: str, eg. 'BTC/USD', ...
                type: str,
                "market" / "limit" / "stop" / "trailing-stop" / "fill-or-kill" /
                "exchange market" / "exchange limit" / "exchange stop" /
                "exchange trailing-stop" / "exchange fill-or-kill"
                (type starting by "exchange" are exchange orders, others are margin trading orders)

                side: str, 'buy'/'sell'
                amount: float
                price: float
                params: {
                    is_hidden: bool, default False, if True, the order will not be listed in orderbook but
                               always pay for taker fee
                    is_postonly: bool, default False, if True, the order will be canceled if a matching
                                order is already in the orderbook, this ensure to always pay for the maker fee
                    use_all_available: bool, default False, if True, the order will use all the available balance
                }
            ccxt response:
            {'amount': 0.002,
             'average': 0.0,
             'datetime': '2018-01-13T13:22:04.224Z',
             'fee': None,
             'filled': 0.0,
             'id': '7139311308',
             'info': {'avg_execution_price': '0.0',
                      'cid': 48124202771,
                      'cid_date': '2018-01-13',
                      'exchange': 'bitfinex',
                      'executed_amount': '0.0',
                      'gid': None,
                      'id': 7139311308,
                      'is_cancelled': False,
                      'is_hidden': False,
                      'is_live': True,
                      'oco_order': None,
                      'order_id': 7139311308,
                      'original_amount': '0.002',
                      'price': '99999.0',
                      'remaining_amount': '0.002',
                      'side': 'sell',
                      'src': 'api',
                      'symbol': 'btcusd',
                      'timestamp': '1515849724.224788405',
                      'type': 'exchange limit',
                      'was_forced': False},
             'price': 99999.0,
             'remaining': 0.002,
             'side': 'sell',
             'status': 'open',
             'symbol': 'BTC/USD',
             'timestamp': 1515849724224,
             'type': 'limit'}

             Return:
             {'amount': 0.00654278,
              'average': 0.0,
              'datetime': datetime.datetime(2018, 3, 12, 10, 27, 32),
              'fee': None,
              'filled': 0.0,
              'id': '9264290876',
              'margin': True,
              'price': 10148.0,
              'remaining': 0.00654278,
              'side': 'sell',
              'status': 'open',
              'symbol': 'BTC/USD',
              'timestamp': 1520850452996,
              'type': 'limit'}
        """
        def is_valid_params(params):
            valid = True
            if 'is_hidden' in params and not isinstance(params['is_hidden'], bool):
                valid = False
            elif 'is_postonly' in params and not isinstance(params['is_hidden'], bool):
                valid = False
            elif 'use_all_available' in params and not isinstance(params['is_hidden'], bool):
                valid = False
            if not valid:
                logger.warning(f"create_order params are invalid: {params}")
            return valid

        self._check_auth()

        if not is_valid_params(params):
            return {}

        if 'use_all_available' in params:
            params['use_all_available'] = 1 if params['use_all_available'] is True else 0

        # Overwrite ccxt function's `type`
        params['type'] = type
        symbol = true_symbol(self.ex, symbol)

        try:
            res = await handle_ccxt_request(
                self.ex.create_order,
                symbol=symbol,
                type=type,
                side=side,
                amount=amount,
                price=price,
                params=params)

        except ccxt.InvalidOrder as err:
            logger.warning(f"{str(err)}")

            if self.notifier:
                await self.notifier.notify_open_orders_failed({
                    "exchange": self.exname,
                    "symbol": symbol,
                    "type": type,
                    "side": side,
                    "amount": amount,
                    "price": price,
                    "timestamp": dt_ms(utc_now()),
                    "margin": self.is_margin_order(type),
                })

            return {}

        order = self.parse_order(res)

        return order

    async def create_order_multi(self, orders):

        def is_valid_order(order):
            valid = True
            if 'symbol' not in order or not isinstance(order['symbol'], str):
                valid = False
            if 'type' not in order or not isinstance(order['type'], str):
                valid = False
            if 'side' not in order or not isinstance(order['side'], str):
                valid = False
            if 'amount' not in order or not isinstance(order['amount'], str):
                if isinstance(order['amount'], int) \
                or isinstance(order['amount'], float):
                    order['amount'] = str(order['amount'])
                else:
                    valid = False
            if 'price' not in order \
            or (not isinstance(order['price'], int)\
            and not isinstance(order['price'], float)):
                valid = False
            if not valid:
                logger.warning(f"create_order_multi orders are invalid: {order}")
            return valid

        self._check_auth()

        for i, order in enumerate(orders):
            if not is_valid_order(order):
                return {}

            order['symbol'] = true_symbol(self.ex, order['symbol'])

            # Convert symbol to bitfinex compatiable one (eg. BTC/USD => BTCUSD)
            orders[i]['symbol'] = self.ex.market_id(order['symbol'])

        params = {
            'orders': orders,
        }

        try:
            res = await handle_ccxt_request(
                self.ex.private_post_order_new_multi,
                params=params)

        except ccxt.InvalidOrder as err:
            logger.warning(f"{str(err)}")

            if self.notifier:
                await self.notifier.notify_log('warn', str(err))

            return {}

        orders = []
        if res['status'] == 'success':
            for order in res['order_ids']:
                market = {'symbol': self.to_ccxt_symbol(order['symbol'])}
                orders.append(
                    self.parse_order(
                        self.ex.parse_order(order, market)))

        return orders

    async def cancel_order(self, id):
        self._check_auth()

        try:
            res = await handle_ccxt_request(self.ex.cancel_order, id)
        except ccxt.OrderNotFound as err:
            logger.warning(f"OrderNotFound: {str(err)}")
            return {}

        ccxt_parsed_order = self.ex.parse_order(res)
        return self.parse_order(ccxt_parsed_order)

    async def cancel_order_multi(self, ids):
        self._check_auth()

        if not isinstance(ids, list):
            raise ValueError(f"Param `ids` must be a list of order ids")

        params = {
            'order_ids': [int(id) for id in ids]
        }
        res = await handle_ccxt_request(self.ex.private_post_order_cancel_multi, params=params)
        return res

    async def cancel_order_all(self):
        self._check_auth()
        res = await handle_ccxt_request(self.ex.private_post_order_cancel_all)
        return res

    async def close_position(self, symbol):
        """ Close positions of a symbol immediately.

            ccxt response:
            [{'message': 'Submitting a market order to liquidate this position.',
            'order':   {'active': 2,
                        'amount': '22.0',
                        'avg_price': '0.0',
                        'cid': None,
                        'cid_date': None,
                        'created_at': '2018-04-22T20:49:46.575830+08:00',
                        'fiat_currency': None,
                        'flags': 0,
                        'gid': None,
                        'hidden': False,
                        'id': 11141572299,
                        'lockedperiod': None,
                        'maxrate': '0.0',
                        'meta': None,
                        'mseq': 0,
                        'nopayback': None,
                        'originalamount': '22.0',
                        'pair': 'XRPUSD',
                        'placed_id': None,
                        'placed_trades': None,
                        'price': None,
                        'price_aux_limit': '0.0',
                        'routing': '',
                        'status': 'ACTIVE (note:POSCLOSE)',
                        'tif': None,
                        'trailingprice': '0.0',
                        'type': 'MARKET',
                        'type_prev': None,
                        'updated_at': '2018-04-22T20:49:46.575830+08:00',
                        'user_id': 398450,
                        'v_pair': 'XRPUSD',
                        'vir': 1},
            'position': {'active': 1,
                        'amount': '-22.0',
                        'base': '0.87855',
                        'created_at': '2018-04-22T20:49:13.000000+08:00',
                        'id': 136543843,
                        'maxrate': '0.0075',
                        'noliquidation': None,
                        'pair': 'XRPUSD',
                        'period': None,
                        'status': 'ACTIVE',
                        'swap': '0.0',
                        'swap_type': 0,
                        'updated_at': '2018-04-22T20:49:13.000000+08:00',
                        'user_id': 398450,
                        'vir': 1}}]

        """
        positions = await self.fetch_positions(symbol)
        res = []

        for pos in positions:
            params = {
                'position_id': pos['id'],
                'amount': str(abs(pos['amount']))
            }
            res.append(await handle_ccxt_request(self.ex.private_post_position_close, params=params))

        return res

    async def _start_my_trade_stream(self, symbol):
        """ Fetch all trades to mongodb. """
        # TODO
        not_implemented()

    async def update_trade_fees(self, once=False):
        """ Periodically update trade fees.
            ccxt response:
            [{'fees': [{'maker_fees': '0.1', 'pairs': 'BTC', 'taker_fees': '0.2'},
                       {'maker_fees': '0.1', 'pairs': 'LTC', 'taker_fees': '0.2'},
                       {'maker_fees': '0.1', 'pairs': 'ETH', 'taker_fees': '0.2'},
                       ...
                       {'maker_fees': '0.1', 'pairs': 'ZRX', 'taker_fees': '0.2'},
                       {'maker_fees': '0.1', 'pairs': 'TNB', 'taker_fees': '0.2'},
                       {'maker_fees': '0.1', 'pairs': 'SPK', 'taker_fees': '0.2'}],
              'maker_fees': '0.1',
              'taker_fees': '0.2'}]

            self.trade_fees = [
                'BTC': {'maker_fees': '0.1', 'taker_fees': '0.2'}},
                ...
            ]
        """
        self._check_auth()

        if once:
            res = await handle_ccxt_request(self.ex.private_post_account_infos)

            fees = {}
            for fee in res[0]['fees']:
                fees[fee['pairs']] = {'maker_fees': float(fee['maker_fees']) / 100,
                                      'taker_fees': float(fee['taker_fees']) / 100}

            self.trade_fees = fees
            return self.trade_fees

        logger.info(f"Start updating trade fees")
        while True:
            if self.log:
                logger.info(f"Update trade fees")

            res = await handle_ccxt_request(self.ex.private_post_account_infos)

            fees = {}
            for fee in res[0]['fees']:
                fees[fee['pairs']] = {'maker_fees': float(fee['maker_fees']) / 100,
                                      'taker_fees': float(fee['taker_fees']) / 100}

            self.trade_fees = fees
            self.ready['trade_fees'] = True
            await asyncio.sleep(self.config['fee_delay'])

    async def update_withdraw_fees(self):
        """ Periodically update withdraw fees.
            ccxt response:
            {'withdraw': {
              'AVT': '0.5',
              'BAT': 0,
              'BCH': '0.0001',
              'BTC': '0.0008',
              'BTG': 0,
              'DAT': '1.0',
              'DSH': '0.01',
              'EDO': '0.5',
              'EOS': '0.1',
              'ETC': '0.01',
              'ETH': '0.01',
              'ETP': '0.01',
              'FUN': 0,
              'GNT': 0,
              'IOT': '0.5',
              'LTC': '0.001',
              'MNA': 0,
              'NEO': 0,
              'OMG': '0.1',
              'QSH': '1.0',
              'QTM': '0.01',
              'SAN': '0.1',
              'SNT': 0,
              'SPK': 0,
              'TNB': 0,
              'XMR': '0.04',
              'XRP': '0.02',
              'YYW': '0.1',
              'ZEC': '0.001',
              'ZRX': 0}}
        """
        self._check_auth()

        logger.info(f"Start updating withdraw fees")
        while True:
            if self.log:
                logger.info(f"Update withdraw fees")

            res = await handle_ccxt_request(self.ex.private_post_account_fees)

            res = res['withdraw']
            fees = {}
            for sym in res:
                fees[sym] = float(res[sym])

            self.withdraw_fees = fees
            self.ready['withdraw_fees'] = True
            await asyncio.sleep(self.config['fee_delay'])

    async def transfer_funds(self, currency, amount, wallet_from, wallet_to):
        """ Transfer funds between exchange, trading(margin), deposit(funding) wallets.
            Param
                currency: str, eg. 'USD', 'BTC'...
                amount: float
                wallet_from: 'exchange', 'margin', 'funding'
                wallet_to: 'exchange', 'margin', 'funding'
        """
        self._check_auth()

        if wallet_from == 'margin':
            walletfrom = 'trading'

        if wallet_from == 'funding':
            walletfrom = 'deposit'

        if wallet_to == 'margin':
            walletto = 'trading'

        if wallet_to == 'funding':
            walletto = 'deposit'

        params = {
            'currency': currency,
            'amount': str(amount),
            'walletfrom': walletfrom,
            'walletto': walletto,
        }

        res = await handle_ccxt_request(self.ex.private_post_transfer, params=params)
        res = res[0]

        if res['status'] == 'success':
            return True
        elif res['status'] == 'error':
            logger.warning(f"Transfer {amount:0.2f} {currency} {wallet_from} -> {wallet_to} failed: "
                           f"{res['message']}")
            return False

    def parse_order(self, order):
        order['margin'] = self.is_margin_order(order['info']['type'])
        order['datetime'] = ms_dt(order['timestamp'])
        order.pop('info', None)
        return order

    @staticmethod
    def is_margin_order(type):
        if not isinstance(type, str):
            raise ValueError("type should be str")

        return True if 'exchange' not in type else False

    def to_ccxt_symbol(self, symbol):
        """ Convert bitinex raw response symbol to ccxt's format. """
        # WARN: Potential bug -- if some symbols used by bitinex is not
        # the same as ccxt may cause exception later on
        qoute = symbol[-3:]
        base = symbol.split(qoute)[0]
        symbol = base.upper() + '/' + qoute.upper()
        symbol = true_symbol(self.ex, symbol)
        return symbol

    async def calc_wallet_value(self):
        """ Calculate total value of all currencies in wallet using latest 1m ohlcv. """
        value = 0

        for curr in self.wallet.keys():
            amount = self.wallet[curr]['exchange']
            amount += self.wallet[curr]['margin']
            amount += self.wallet[curr]['funding']
            value += await self.calc_value_of(curr, amount)

        return value

    async def calc_order_value(self):
        """ Calulate total value of all open orders. """
        MR = self._config['trading'][self.exname]['margin_rate']

        orders = await self.fetch_open_orders()
        value = 0

        for order in orders:
            order_val = order['price'] * abs(order['remaining'])

            if order['margin']:
                order_val /= MR

            value += order_val

        return value

    async def calc_all_position_value(self, include_pl=True):
        """ Calculate total value of all open positions. """
        MR = self._config['trading'][self.exname]['margin_rate']

        positions = await self.fetch_positions()
        value = 0

        for pos in positions:
            base_cost = pos['base_price'] * abs(pos['amount']) / MR

            if include_pl:
                value += base_cost + pos['pl']
            else:
                value += base_cost

        return value