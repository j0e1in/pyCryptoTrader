from concurrent.futures import FIRST_COMPLETED
from sanic import Sanic
from sanic import response
from sanic.exceptions import abort

import asyncio
import argparse
import copy
import logging
import inspect
import json

from utils import dt_ms, config, dummy_data

logger = logging.getLogger('pyct.')
log_fmt = "%(asctime)s | %(name)s | %(levelname)5s | %(status)d | %(request)s | %(message)s"

class APIServer():

    ## Sanic default built-in configuration
    # | Variable           | Default   | Description                                   |
    # | ------------------ | --------- | --------------------------------------------- |
    # | REQUEST_MAX_SIZE   | 100000000 | How big a request may be (bytes)              |
    # | REQUEST_TIMEOUT    | 60        | How long a request can take to arrive (sec)   |
    # | RESPONSE_TIMEOUT   | 60        | How long a response can take to process (sec) |
    # | KEEP_ALIVE         | True      | Disables keep-alive when False                |
    # | KEEP_ALIVE_TIMEOUT | 5         | How long to hold a TCP connection open (sec)  |

    app = Sanic(__name__, log_config=None)

    def __init__(self, trader, custom_config=None):
        self._config = custom_config if custom_config else config
        self.config = self._config['apiserver']

        self.api_access = self.config['api_access']

        self.app.trader = trader
        self.app.server = self
        self.app.config.KEEP_ALIVE = config['apiserver']['keep_alive']
        self.app.config.KEEP_ALIVE_TIMEOUT = config['apiserver']['keep_alive_timeout']
        self.app.config.REQUEST_TIMEOUT = config['apiserver']['request_timeout']
        self.app.config.RESPONSE_TIMEOUT = config['apiserver']['response_timeout']

        self.log_level = 'info'

    async def run(self, host='0.0.0.0', port=8000, enable_ssl=False, *args, **kwargs):
        """ Start server and provide some cli options. """

        # Sanic.create_server options
        # create_server(host=None,
        #               port=None,
        #               debug=False,
        #               ssl=None,
        #               sock=None,
        #               protocol=None,
        #               backlog=100,
        #               stop_event=None,
        #               access_log=True)

        if enable_ssl:
            import ssl
            context = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
            context.load_cert_chain(self.config['cert'], keyfile=self.config['key'])

        else:
            context = None

        start_server = self.app.create_server(host=host, port=port, ssl=context, *args, **kwargs)
        start_trader = asyncio.ensure_future(self.app.trader.start())

        with_ssl = 'with' if enable_ssl else 'without'
        logger.info(f"Starting API server {with_ssl} SSL...")

        await asyncio.gather(
            start_server,
            start_trader,
        )

    @app.listener('after_server_stop')
    async def after_server_stop(app, loop):
        await app.trader.ex.ex.close()

    @app.route('/account/info/<uid:string>/<ex:string>', methods=['GET'])
    async def account_info(req, uid, ex):
        """ Query current exchange account's trading state.
            {
                "balance": {
                    "USD": `float` or `{'exchange': float, 'margin': float, 'funding': float}`,
                    ...
                },
                "active_markets": [
                    {
                        "symbol": string
                        "start_timestamp": string
                        "margin": bool (margin trading availability)
                    },
                    ...
                ],
                "inactive_markets": [
                    {
                        "symbol": string
                        "margin": bool (margin trading availability)
                    },
                    ...
                ]
            }
        """
        if not req.app.server.verified_access(uid, inspect.stack()[0][3]):
            abort(401)

        if not req.app.trader.ex.is_ready():
            return response.json({ 'error': 'Not ready' })

        if ex != req.app.trader.ex.exname:
            return response.json({ 'error': 'Exchange is not active.' })

        trader = req.app.trader
        active_markets = trader.ex.markets
        all_markets = list(trader.ex.ex.markets.keys())
        inactive_markets = [m for m in all_markets if m not in active_markets]

        active = []
        inactive = []

        for market in active_markets:
            active.append({
                'symbol': market,
                'start_timestamp': dt_ms(trader.ex.markets_start_dt[market]),
                'margin': trader.ex.ex.markets[market]['info']['margin']
            })

        for market in inactive_markets:
            inactive.append({
                'symbol': market,
                'start_timestamp': None,
                'margin': trader.ex.ex.markets[market]['info']['margin']
            })

        return response.json({
            'balance': trader.ex.wallet,
            'active_markets': active,
            'inactive_markets': inactive,
        })

    @app.route('/account/summary/<uid:string>/<ex:string>', methods=['GET'])
    async def account_summary(req, uid, ex):
        """ Query summary of current trading session.

            Response:
            {
                "start": timestamp, (bot trading start datetime)
                "now": timestamp, (datetime as of summary calculation)
                "days": int,
                "#profit_trades": int,
                "#loss_trades": int,
                "initial_balance": {
                    "USD": `float` or `{'exchange': float, 'margin': float, 'funding': float}`,
                    "BTC": `float` or `{'exchange': float, 'margin': float, 'funding': float}`,
                    ...
                },
                "initial_value": float,
                "current_balance": {
                    "USD": `float` or `{'exchange': float, 'margin': float, 'funding': float}`,
                    "BTC": `float` or `{'exchange': float, 'margin': float, 'funding': float}`,
                    ...
                },
                "current_value": float,
                "total_fee": float,
                "total_margin_fee": float,
                "PL": float,
                "PL(%)": float,
                "PL_Eff": float
            }
        """
        if not req.app.server.verified_access(uid, inspect.stack()[0][3]):
            abort(401)

        if not req.app.trader.ex.is_ready():
            return response.json({ 'error': 'Not ready' })

        if ex != req.app.trader.ex.exname:
            return response.json({ 'error': 'Exchange {ex} is not active.' })

        summ = copy.deepcopy(await req.app.trader.get_summary())
        summ['start'] = dt_ms(summ['start'])
        summ['now'] = dt_ms(summ['now'])

        return response.json(summ)

    @app.route('/account/active/orders/<uid:string>/<ex:string>', methods=['GET'])
    async def active_orders(req, uid, ex):
        """ Query active orders of an exchange.
            {
                "orders": [
                    {
                        "symbol": string
                        "type": string
                        "side": string
                        "amount": float
                        "filled": float
                        "remaining": float
                        "price": float
                        "value" float
                        "timestamp": int
                        "margin": bool
                    },
                    ...
                ]
            }
        """
        if not req.app.server.verified_access(uid, inspect.stack()[0][3]):
            abort(401)

        if ex != req.app.trader.ex.exname:
            return response.json({ 'error': 'Exchange is not active.' })

        if 'dummy-data' in req.headers \
        and req.headers['dummy-data'] == 'true':
            return response.json(dummy_data['active_orders'])

        orders = await req.app.trader.ex.fetch_open_orders()

        for ord in orders:
            ord['value'] = abs(ord['amount']) * ord['price']
            del ord['average']
            del ord['datetime']
            del ord['fee']
            del ord['id']
            del ord['status']

        return response.json({ 'orders': orders })

    @app.route('/account/active/positions/<uid:string>/<ex:string>', methods=['GET'])
    async def active_positions(req, uid, ex):
        """ Query active orders of an exchange.
            {
                "positions": [
                    {
                        "symbol": string
                        "side": string
                        "amount": float
                        "price": float
                        "value": float
                        "timestamp": string
                        "PL": float
                    },
                    ...
                ]
            }
        """
        if not req.app.server.verified_access(uid, inspect.stack()[0][3]):
            abort(401)

        trader = req.app.trader

        if ex != trader.ex.exname:
            return response.json({ 'error': 'Exchange is not active.' })

        if 'dummy-data' in req.headers \
        and req.headers['dummy-data'] == 'true':
            return response.json(dummy_data['active_positions'])

        positions = await trader.ex.fetch_positions()

        for i, pos in enumerate(positions):
            margin_rate = trader.config[trader.ex.exname]['margin_rate']
            base_value = abs(pos['amount']) / margin_rate * pos['base_price']

            positions[i] = {
                'symbol': pos['symbol'],
                'side': 'buy' if pos['amount'] > 0 else 'sell',
                'amount': abs(pos['amount']) / margin_rate,
                'price': pos['base_price'],
                'value': base_value,
                'timestamp': pos['timestamp'],
                'PL': pos['pl'],
                'PL(%)': pos['pl'] / base_value * 100,
            }

        return response.json({ 'positions': positions })

    @app.route('/ping', methods=['GET'])
    async def ping(req):
        return response.json({ 'ok': True })

    ############################
    ##       2FA Required     ##
    ############################

    @app.route('/notification/log_level/<uid:string>', methods=['POST'])
    async def change_log_level(req, uid):
        if not req.app.server.verified_access(uid, inspect.stack()[0][3]):
            abort(401)

        payload = req.json
        if 'level' not in payload:
            return response.json({
                'error': "Payload should contain field `level` "
                         "with one of values: info | debug | warn | error"
            })

        req.app.server.log_level = payload['level']
        return response.json({'ok': True})

    @app.route('/trading/max_fund/<uid:string>', methods=['POST'])
    async def change_max_fund(req, uid):
        if not req.app.server.verified_access(uid, inspect.stack()[0][3]):
            abort(401)

        payload = req.json
        if 'fund' not in payload:
            return response.json({
                'error': "Payload should contain field `fund` with a float value"
            })

        req.app.trader.max_fund = payload['fund']
        logger.debug(f'max fund is set to {req.app.trader.max_fund}')
        return response.json({'ok': True})

    @app.route('/trading/markets/enable/<uid:string>/<ex:string>', methods=['POST'])
    async def enable_markets(req, uid, ex):
        if not req.app.server.verified_access(uid, inspect.stack()[0][3]):
            abort(401)

        trader = req.app.trader
        payload = req.json

        if 'markets' not in payload or not isinstance(payload['markets'], list):
            return response.json({
                'error': "Payload should contain field `markets` with a list of strings"
            })

        not_supported = []

        for market in payload['markets']:
            if market not in trader.ex.markets:
                if market in trader.config[trader.ex.exname]['markets_all']:
                    trader.add_market(market)
                    logger.info(f"{ex} {market} enabled")
                else:
                    not_supported.append(market)

        if len(not_supported) > 0:
            return response.json({
                'error': 'Some markets are not supported',
                'markets': not_supported
            })
        else:
            return response.json({ 'ok': True })

    @app.route('/trading/markets/disable/<uid:string>/<ex:string>', methods=['POST'])
    async def disable_markets(req, uid, ex):
        if not req.app.server.verified_access(uid, inspect.stack()[0][3]):
            abort(401)

        trader = req.app.trader
        payload = req.json

        if 'markets' not in payload or not isinstance(payload['markets'], list):
            return response.json({
                'error': "Payload should contain field `markets` with a list of strings"
            })

        not_supported = []

        for market in payload['markets']:
            if market in trader.ex.markets:
                trader.remove_market(market)
                logger.info(f"{ex} {market} disabled")

            if market not in trader.config[trader.ex.exname]['markets_all']:
                not_supported.append(market)

        if len(not_supported) > 0:
            return response.json({
                'error': 'Some markets are not supported',
                'markets': not_supported
            })
        else:
            return response.json({'ok': True})

    @app.route('/trading/enable/<uid:string>', methods=['POST'])
    async def enable_trading(req, uid):
        if not req.app.server.verified_access(uid, inspect.stack()[0][3]):
            abort(401)

        req.app.trader.enable_trade = True
        logger.info(f"Trading enabled")

        return response.json({ 'ok': True })

    @app.route('/trading/disable/<uid:string>', methods=['POST'])
    async def disable_trading(req, uid):
        if not req.app.server.verified_access(uid, inspect.stack()[0][3]):
            abort(401)

        req.app.trader.enable_trade = False
        logger.info(f"Trading disabled")

        return response.json({ 'ok': True })

    def verified_access(self, uid, func):
        if uid in self.api_access:
            if func in self.api_access[uid]['deny']:
                return False

            elif ("all" in self.api_access[uid]['allow'] \
            or    func in self.api_access[uid]['allow']):
                return True

        return False
