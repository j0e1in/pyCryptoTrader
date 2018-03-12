from concurrent.futures import FIRST_COMPLETED
from sanic import Sanic
from sanic.response import json

import asyncio
import argparse
import copy

from utils import dt_ms


class APIServer():

    app = Sanic(__name__, log_config=None)

    def __init__(self, trader):
        self.app.trader = trader
        # setattr(self.app, 'trader', trader) # for app listener and router

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

    @app.route('/account/summary')
    async def account_summary(req):
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
        summ = copy.deepcopy(await req.app.trader.get_summary())
        summ['start'] = dt_ms(summ['start'])
        summ['now'] = dt_ms(summ['now'])

        return json(summ)