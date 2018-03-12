from concurrent.futures import FIRST_COMPLETED
from sanic import Sanic
from sanic import response
from sanic.exceptions import abort

import asyncio
import argparse
import copy
import json

from utils import dt_ms, config


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

    async def run(self, *args, **kwargs):
        """ Start server and provide some cli options. """

        parser = argparse.ArgumentParser()
        parser.add_argument('--host', default='0.0.0.0', help='Server IP')
        parser.add_argument('--port', type=int, default=8000, help='Server port')
        cli_args = parser.parse_args()

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

        start_server = self.app.create_server(host=cli_args.host, port=cli_args.port, *args, **kwargs)
        start_trader = asyncio.ensure_future(self.app.trader.start())

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
        if not req.app.server.verified_access(uid, 'account_info'):
            abort(401)

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
                "#normal_orders": int,
                "#margin_orders": int,
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
        if not req.app.server.verified_access(uid, 'account_summary'):
            abort(401)

        if ex != req.app.trader.ex.exname:
            return response.json({ 'error': 'Exchange is not active.' })

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
                        "timestamp": int
                        "margin": bool
                    },
                    ...
                ]
            }
        """
        if not req.app.server.verified_access(uid, 'active_orders'):
            abort(401)

        if ex != req.app.trader.ex.exname:
            return response.json({ 'error': 'Exchange is not active.' })

        orders = await req.app.trader.ex.fetch_open_orders()

        for ord in orders:
            del ord['average']
            del ord['datetime']
            del ord['fee']
            del ord['id']
            del ord['status']

        return response.json({ 'orders': orders })

    @app.route('/account/active/positions/<uid:string>/<ex:string>', methods=['GET'])
    async def active_positions(req, uid, ex):
        """ Query active orders of an exchange.
        """
        if not req.app.server.verified_access(uid, 'active_positions'):
            abort(401)

        if ex != req.app.trader.ex.exname:
            return response.json({ 'error': 'Exchange is not active.' })

        positions = await req.app.trader.ex.fetch_positions()

        for i, pos in enumerate(positions):
            positions[i] = {
                'amount': abs(pos['amount']),
                'base_price': pos['base_price'],
                'PL': pos['pl'],
                'side': 'buy' if pos['amount'] > 0 else 'sell',
                'symbol': pos['symbol'],
                'timestamp': pos['timestamp']
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
        if not req.app.server.verified_access(uid, 'change_log_level'):
            abort(401)

        payload = json.loads(req.body)
        if 'level' not in payload:
            return response.json({ 'error': "Payload should contain field `level`"
                                  " with one of values: info | debug | warn | error" })

        req.app.server.log_level = payload['level']
        return response.json({'ok': True})

    def verified_access(self, uid, func):
        if uid in self.api_access \
        and ("all" in self.api_access[uid] \
        or    func in self.api_access[uid]):
            return True
        else:
            return False
