from sanic import Sanic
from sanic.response import json

import asyncio
import argparse

from utils import dt_ms


class APIServer():

    app = Sanic(__name__)

    def __init__(self, trader, *args, **kwargs):
        self.app.trader = trader
        # setattr(self.app, 'trader', trader) # for app listener and router

    async def run(self):
        """ Start server and provide some cli options. """

        parser = argparse.ArgumentParser()
        parser.add_argument('--host', default='0.0.0.0', help='Server IP')
        parser.add_argument('--port', type=int, default=8000, help='Server port')
        args = parser.parse_args()

        start_server = self.app.create_server(host=args.host, port=args.port)
        start_trader = asyncio.ensure_future(self.app.trader.start())

        await asyncio.gather(
            start_server,
            start_trader,
        )

    @app.listener('after_server_stop')
    async def after_server_stop(app, loop):
        await app.trader.ex.ex.close()

    @app.route('/account/info')
    async def account_info(req):
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

        return json({
            'balance': trader.ex.wallet,
            'active_markets': active,
            'inactive_markets': inactive,
        })