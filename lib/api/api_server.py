from concurrent.futures import FIRST_COMPLETED
from sanic import response
from sanic.exceptions import abort

import asyncio
import argparse
import copy
import logging
import inspect
import json
import numpy as np
import sanic

from api.auth import AuthyManager
from utils import \
    dt_ms, \
    config, \
    load_json, \
    log_config, \
    register_logging_file_handler

logger = logging.getLogger('pyct')


dummy_data = load_json(config['dummy_data_file'])

def customized_sanic_log_config():
    config = sanic.log.LOGGING_CONFIG_DEFAULTS

    config['formatters']['generic']['datefmt'] = \
        log_config['formatters']['pyct_colored']['datefmt']
    config['formatters']['generic']['format'] = \
        log_config['formatters']['pyct_colored']['format']
    config['formatters']['access']['datefmt'] = \
        log_config['formatters']['pyct_colored']['datefmt']
    config['formatters']['access']['format'] = \
        "%(asctime)s | %(levelname)s | %(request)s %(message)s %(status)d %(byte)d"

    return config


class APIServer():

    ## Sanic default built-in configuration
    # | Variable           | Default   | Description                                   |
    # | ------------------ | --------- | --------------------------------------------- |
    # | REQUEST_MAX_SIZE   | 100000000 | How big a request may be (bytes)              |
    # | REQUEST_TIMEOUT    | 60        | How long a request can take to arrive (sec)   |
    # | RESPONSE_TIMEOUT   | 60        | How long a response can take to process (sec) |
    # | KEEP_ALIVE         | True      | Disables keep-alive when False                |
    # | KEEP_ALIVE_TIMEOUT | 5         | How long to hold a TCP connection open (sec)  |

    app = sanic.Sanic(__name__, log_config=customized_sanic_log_config())

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
        self.authy = AuthyManager(trader.mongo)

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
        logger.info(f"Starting API server {with_ssl} SSL")

        await asyncio.gather(
            start_server,
            start_trader,
        )

    @app.listener('after_server_stop')
    async def after_server_stop(app, loop):
        await app.trader.ex.ex.close()

    @app.route('/authy/create_user', methods=['POST'])
    async def authy_create_user(req):
        """ Add authy user to database, and authy will send 2FA to their account. """
        # TODO: use payload info to verify access
        # if not req.app.server.verified_access(uid, inspect.stack()[0][3]):
        #     abort(401)

        payload = req.json
        if not payload \
        or 'email' not in payload \
        or 'phone' not in payload \
        or 'country_code' not in payload:
            return response.json({
                'error': "Payload should contain fields "
                         "`email`, `phone` and `country_code`"
            })

        succ, res = await req.app.server.authy.create_user(
            payload['email'],
            payload['phone'],
            payload['country_code']
        )
        if succ:
            return response.json({'ok': True})
        else:
            return response.json({'error': res})


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
        orders = api_parse_orders(orders)

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
        positions = api_parse_positions(
            positions, trader.config[trader.ex.exname]['margin_rate'])

        return response.json({ 'positions': positions })

    @app.route('/trading/signals/<uid:string>/<ex:string>', methods=['GET'])
    async def trading_signals(req, uid, ex):
        """ Query active orders of an exchange.
            {
                "signals": {
                    "BTC/USD": [ // Contain recent N signals
                        {
                            "timestamp": string
                            "signal": "buy", "sell", "close", "none"
                        },
                        ...
                    ],
                    "ETH/USD": [...]
                }
            }
        """
        if not req.app.server.verified_access(uid, inspect.stack()[0][3]):
            abort(401)

        if not req.app.trader.ex.is_ready():
            return response.json({ 'error': 'Not ready' })

        trader = req.app.trader

        if ex != trader.ex.exname:
            return response.json({ 'error': 'Exchange is not active.' })

        try:
            sigs = await trader.strategy.run()
        except Exception:
            return response.json({ 'error': 'Not ready' })

        signals = {}

        for market in sigs:
            signals[market] = []
            for dt, sig in sigs[market][-12:].items():
                action = ''

                if np.isnan(sig):
                    action = 'none'
                elif sig > 0:
                    action = 'buy'
                elif sig < 0:
                    action = 'sell'
                elif sig == 0:
                    action = 'close'

                signals[market].append({
                    'timestamp': dt_ms(dt),
                    'signal': action
                })

        return response.json(signals)

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
        if not payload or 'level' not in payload:
            return response.json({
                'error': "Payload should contain field `level` "
                         "with one of values: info | debug | warn | error"
            })

        req.app.server.log_level = payload['level']
        return response.json({'ok': True})

    @app.route('/notification/large_pl/<uid:string>', methods=['POST'])
    async def change_large_pl_threshold(req, uid):
        if not req.app.server.verified_access(uid, inspect.stack()[0][3]):
            abort(401)

        payload = req.json
        if not payload or 'PL(%)' not in payload:
            return response.json({
                'error': "Payload should contain field `PL(%)`"
            })

        req.app.server.trader._config['apiclient']['large_pl_threshold'] = payload['PL(%)']
        return response.json({'ok': True})

    @app.route('/trading/max_fund/<uid:string>', methods=['POST'])
    async def change_max_fund(req, uid):
        if not req.app.server.verified_access(uid, inspect.stack()[0][3]):
            abort(401)

        payload = req.json
        if not payload or 'fund' not in payload:
            return response.json({
                'error': "Payload should contain field `fund` with a float value"
            })

        msg = f"Change max fund to ${payload['fund']}"
        accept, res = await req.app.server.send_2fa_request(uid, msg)

        if not accept:
            return res

        req.app.trader.max_fund = payload['fund']
        logger.debug(f'max fund is set to {req.app.trader.max_fund}')
        return response.json({'ok': True})

    @app.route('/trading/markets/enable/<uid:string>/<ex:string>', methods=['POST'])
    async def enable_markets(req, uid, ex):
        if not req.app.server.verified_access(uid, inspect.stack()[0][3]):
            abort(401)

        trader = req.app.trader
        payload = req.json

        if not payload or 'markets' not in payload or not isinstance(payload['markets'], list):
            return response.json({
                'error': "Payload should contain field `markets` with a list of strings"
            })

        markets = [str(market) for market in payload['markets']]
        msg = "Enable markets " + ', '.join(markets)
        accept, res = await req.app.server.send_2fa_request(uid, msg)

        if not accept:
            return res

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

        if not payload or 'markets' not in payload or not isinstance(payload['markets'], list):
            return response.json({
                'error': "Payload should contain field `markets` with a list of strings"
            })

        markets = [str(market) for market in payload['markets']]
        msg = "Disable markets: " + ', '.join(markets)
        accept, res = await req.app.server.send_2fa_request(uid, msg)

        if not accept:
            return res

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

        msg = "Enable trading"
        accept, res = await req.app.server.send_2fa_request(uid, msg)

        if not accept:
            return res

        # req.app.trader.enable_trading = True
        logger.info(f"Trading enabled")

        return response.json({ 'ok': True })

    @app.route('/trading/disable/<uid:string>', methods=['POST'])
    async def disable_trading(req, uid):
        if not req.app.server.verified_access(uid, inspect.stack()[0][3]):
            abort(401)

        msg = "Disable trading"
        accept, res = await req.app.server.send_2fa_request(uid, msg)

        if not accept:
            return res

        req.app.trader.enable_trading = False
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

    async def send_2fa_request(self, uid, msg):
        # Convert uid to userid
        # and check if the userid is in mongodb
        userid = self.authy.get_userid(uid)
        if not userid \
        or not await self.authy.user_exist(userid):
            return False, response.json({'error': f'Authy user does not exist.'})

        res, status = await self.authy.one_touch(userid, msg)
        if not res:
            return False, response.json(
                {'error': f'2FA request {status}'})
        else:
            return True, ''


def api_parse_orders(orders):
    for ord in orders:
        ord['value'] = abs(ord['amount']) * ord['price']
        ord.pop('average', None)
        ord.pop('datetime', None)
        ord.pop('fee', None)
        ord.pop('id', None)
        ord.pop('status', None)
        ord.pop('filled', None)
        ord.pop('remaining', None)

    return orders


def api_parse_positions(positions, margin_rate):
    if not positions:
        return positions

    if not isinstance(positions, list):
        positions = [positions]

    price_name = 'base_price' if 'base_price' in positions[0] else 'price'
    pl_name = 'pl' if 'pl' in positions[0] else 'PL'

    for i, pos in enumerate(positions):
        base_value = abs(pos['amount']) / margin_rate * pos[price_name]

        positions[i] = {
            'symbol': pos['symbol'],
            'side': 'buy' if pos['amount'] > 0 else 'sell',
            'amount': abs(pos['amount']) / margin_rate,
            'price': pos[price_name],
            'value': base_value,
            'timestamp': pos['timestamp'],
            'PL': pos[pl_name],
            'PL(%)': pos[pl_name] / base_value * 100,
        }

    return positions
