from sanic import Sanic
from sanic.response import json

import asyncio
import argparse


class APIServer():

    app = Sanic(__name__)

    def __init__(self, trader, *args, **kwargs):
        self.trader = trader
        self.ex = trader.ex

    async def run(self):
        """ Start server and provide some cli options. """

        parser = argparse.ArgumentParser()
        parser.add_argument('--host', default='0.0.0.0', help='Server IP')
        parser.add_argument('--port', type=int, default=8000, help='Server port')
        args = parser.parse_args()

        start_server = self.app.create_server(host=args.host, port=args.port)
        start_trader = asyncio.ensure_future(self.trader.start())

        await asyncio.gather(
            start_server,
            start_trader,
        )

    @app.listener('after_server_stop')
    async def after_server_stop(app, loop):
        await app.trader.ex.ex.close()

    @app.route('/account/info')
    async def account_info(req):
        return json({'text': 'hell!'})