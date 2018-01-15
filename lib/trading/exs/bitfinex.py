from pprint import pprint
import ccxt.async as ccxt
import copy
import logging

from trading.exs.exbase import EXBase
from utils import ms_dt, \
                  dt_ms, \
                  not_implemented, \
                  execute_mongo_ops, \
                  sec_ms

from ipdb import set_trace as trace

logger = logging.getLogger()


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

    def __init__(self, mongo, apikey=None, secret=None, custom_config=None, verbose=False):
        super().__init__(mongo, 'bitfinex', apikey, secret, custom_config=custom_config, verbose=verbose)

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

        res = await self._send_ccxt_request(self.ex.fetch_balance)
        for curr in res['info']:
            sym = str.upper(curr['currency'])

            if sym not in self.wallet:
                self.wallet[sym] = {'exchange': 0, 'margin': 0, 'funding': 0}

            if curr['type'] == 'exchange':
                self.wallet[sym]['exchange'] = curr['available']
            elif curr['type'] == 'trading':
                self.wallet[sym]['margin'] = curr['available']
            elif curr['type'] == 'deposit':
                self.wallet[sym]['funding'] = curr['available']
            else:
                self.wallet[sym][curr['type']] = curr['available']

        self.ready['wallet'] = True
        return self.wallet

    async def _start_orderbook_stream(self, log=False):
        params = {
            'limit_bids': self.config['orderbook_size'],
            'limit_asks': self.config['orderbook_size'],
            'group': 1, # 0 / 1
        }
        await super()._start_orderbook_stream(log=log, params=params)

    async def get_orderbook(self, symbol, log=False):
        params = {
            'limit_bids': self.config['orderbook_size'],
            'limit_asks': self.config['orderbook_size'],
            'group': 1, # 0 / 1
        }
        return await super().get_orderbook(symbol, log=log, params=params)

    async def update_markets(self):
        """
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
        res = await self._send_ccxt_request(self.ex.fetch_markets)
        for mark in res:
            if mark['symbol'] in self.markets:
                self.markets_info[mark['symbol']] = mark

        self.ready['markets'] = True
        return self.markets_info

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
        """
        self._check_auth()

        res = await self._send_ccxt_request(self.ex.fetch_open_orders, symbol)

        orders = []
        for ord in res:
            ord = self.parse_order(ord)
            orders.append(ord)

        return orders

    async def fetch_closed_orders(self,  symbol=None):
        self._check_auth()
        not_implemented()
        # Bug: empty response
        # res = await self._send_ccxt_request(self.ex.fetch_closed_orders, symbol)
        # return res

    async def fetch_order(self, id, parse=True):
        """ Fetch a single order using order known id.
            Param
                id: str, id of an order
                parse: bool, if False, original ccxt response will be returned directly
        """
        self._check_auth()
        ord = await self._send_ccxt_request(self.ex.fetch_order, id)
        return self.parse_order(ord) if parse is True else ord

    async def fetch_positions(self, symbol=None):
        """
            ccxt response
            [{'amount': '0.002',
              'base': '13219.0',
              'id': 134256839,
              'pl': '-0.076828',
              'status': 'ACTIVE',
              'swap': '0.0',
              'symbol': 'btcusd',
              'timestamp': '1515947276.0'}]
        """
        def parse_position(position):
            pos['symbol'] = self.to_ccxt_symbol(pos['symbol'])
            pos['timestamp'] = sec_ms(pos['timestamp'])
            pos['datetime'] = ms_dt(pos['timestamp'])

        self._check_auth()
        res = await self._send_ccxt_request(self.ex.private_post_positions)

        positions = []
        for pos in res:
            parse_position(pos)

            if not symbol:
                positions.append(pos)
            elif pos['symbol'] == symbol:
                positions.append(pos)

        return positions

    async def fetch_my_recent_trades(self, symbol, start=None, end=None, limit=1000):
        """ Fetch most recent N trades.
            ccxt response:
            {'amount': 0.52,
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
        """
        self._check_auth()

        start = dt_ms(start) if start else None
        end = dt_ms(end) if end else None

        params = {}
        params['reverse'] = 1
        if end:
            params['until'] = end

        res = await self._send_ccxt_request(self.ex.fetch_my_trades, symbol, start, limit, params)

        trades = []
        for trade in res:
            trade['fee'] = abs(float(trade['info']['fee_amount']))
            trade['fee_currency'] = trade['info']['fee_currency']
            trade['datetime'] = ms_dt(trade['timestamp'])
            del trade['info']
            trades.append(trade)

        return trades

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

        res = await self._send_ccxt_request(self.ex.fetch_deposit_address, currency, params)

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

        res = await self._send_ccxt_request(self.ex.create_deposit_address, currency, params)

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
                logger.warn(f"create_order params are invalid: {params}")
            return valid

        self._check_auth()

        if not is_valid_params(params):
            return {}

        if 'use_all_available' in params:
            params['use_all_available'] = 1 if params['use_all_available'] is True else 0

        # Overwrite ccxt function's `type`
        params['type'] = type

        try:
            res = await self._send_ccxt_request(self.ex.create_order,
                                          symbol=symbol,
                                          type=type,
                                          side=side,
                                          amount=amount,
                                          price=price,
                                          params=params)
        except ccxt.InvalidOrder as err:
            logger.warn(f"{str(err)}")
            # TODO: pass invalid order msg to client: MessengerServer.handle_invalid_error(err, order)
            return {}

        order = self.parse_order(res)
        return order

    async def cancel_order(self, id):
        self._check_auth()

        try:
            res = await self._send_ccxt_request(self.ex.cancel_order, id)
        except ccxt.OrderNotFound as err:
            logger.warn(f"OrderNotFound: {str(err)}")
            return {}

        ccxt_parsed_order = self.ex.parse_order(res)
        return self.parse_order(ccxt_parsed_order)

    async def cancel_order_multi(self, ids):
        self._check_auth()

        if not isinstance(ids, list):
            raise ValueError(f"Param `ids` must be a list of order ids")

        params = {
            'order_ids': ids
        }
        res = await self._send_ccxt_request(self.ex.private_post_order_cancel_multi, params=params)
        return res

    async def cancel_order_all(self):
        self._check_auth()
        res = await self._send_ccxt_request(self.ex.private_post_order_cancel_all)
        return res

    async def _start_my_trade_stream(self, symbol, log=False):
        """ Fetch all trades to mongodb. """
        not_implemented()

    def parse_order(self, order):
        order['margin'] = self.is_margin_order(order)
        order['datetime'] = ms_dt(order['timestamp'])
        del order['info']
        return order

    @staticmethod
    def is_margin_order(order):
        return True if 'exchange' not in order['info']['type'] else False

    @staticmethod
    def to_ccxt_symbol(symbol):
        """ Convert bitinex raw response symbol to ccxt's format. """
        # WARN: Potential bug -- if some symbols used by bitinex is not
        # the same as ccxt may cause exception later on
        qoute = symbol[-3:]
        base = symbol.split(qoute)[0]
        symbol = base.upper() + '/' + qoute.upper()
        return symbol
