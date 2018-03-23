from hashlib import sha1

import aiohttp
import base64
import copy
import hmac
import logging
import json

from api.api_server import api_parse_orders, api_parse_positions
from utils import config, load_keys

logger = logging.getLogger('pyct')


class Messenger():

    def __init__(self, trader, custom_config=None, ssl=True):
        self._config = custom_config if custom_config else config
        self.config = self._config['apiclient']
        self.trader = trader

        self.session = aiohttp.ClientSession()
        self.secret = load_keys(trader.id)['FB_APP_SECRET']

        self.default = {}
        self.default['header'] = {
            'Content-Type': 'application/json',
            'x-hub-signature': '',
        }
        self.default['payload'] = {
            'signature': 'trader'
        }
        url_prefix = 'https://' if ssl else 'http://'
        self.base_url = url_prefix + self.config['messenger_host']

    async def notify_open_orders_succ(self, orders):
        """ Send successfully opened (scale) orders
            Send:
            {
                "orders": [
                    {
                        "exchange": string
                        "symbol": string
                        "type": string
                        "side": string
                        "amount": float
                        "price": float
                        "timestamp": string
                        "margin": bool,
                    },
                    ...
                ],
                "summary": {
                    "exchange": string
                    "symbol": string
                    "type": string
                    "side": string
                    "amount": float (total amount)
                    "price": float (average price)
                    "timestamp": string
                    "margin": bool,
                }
            }
        """
        if not isinstance(orders, list):
            orders = [orders]

        summary = {
            'exchange': self.trader.ex.exname,
            'symbol': orders[0]['symbol'],
            'type': orders[0]['type'],
            'side': orders[0]['side'],
            'amount': 0,
            'price': 0,
            'timestamp': orders[0]['timestamp'],
            'margin': orders[0]['margin'],
        }

        orders = api_parse_orders(orders)

        for order in orders:
            order['exchange'] = self.trader.ex.exname

            summary['amount'] += order['amount']
            summary['price'] += order['price']

        summary['price'] /= len(orders)

        route = f"/notification/order/open/{self.trader.id}"
        payload = {'orders': orders, 'summary': summary}

        return await self.request('post', route, payload)

    async def notify_open_orders_failed(self, orders):
        """ Send failed to open orders
            Send:
            {
                "orders": [
                    {
                    "exchange": string
                    "symbol": string
                    "type": string
                    "side": string
                    "amount": float
                    "price": float
                    "timestamp": string
                    "margin": bool,
                    },
                    ...
                ],
                "summary": {
                    "exchange": string
                    "symbol": string
                    "type": string
                    "side": string
                    "amount": float (total amount)
                    "price": float (average price)
                    "timestamp": string
                    "margin": bool,
                }
            }
        """
        if not isinstance(orders, list):
            orders = [orders]

        summary = {
            'exchange': self.trader.ex.exname,
            'symbol': orders[0]['symbol'],
            'type': orders[0]['type'],
            'side': orders[0]['side'],
            'amount': 0,
            'price': 0,
            'timestamp': orders[0]['timestamp'],
            'margin': orders[0]['margin'],
        }

        orders = api_parse_orders(orders)

        for order in orders:
            order['exchange'] = self.trader.ex.exname

            summary['amount'] += order['amount']
            summary['price'] += order['price']

        summary['price'] /= len(orders)

        route = f"/notification/order/failed/{self.trader.id}"
        payload = {'orders': orders, 'summary': summary}

        return await self.request('post', route, payload)

    async def notify_orders_cancel(self, orders):
        pass

    async def notify_position_close(self, positions):
        pass

    async def notify_position_danger(self, positions):
        """ Warn for danger positions
            Send:
            {
                "positions": [
                    {
                        "exchange": string
                        "symbol": string
                        "side": string
                        "amount": float
                        "price": float
                        "value": float
                        "timestamp": string,
                        "PL": float
                        "PL(%)": float
                    },
                    ...
                ]
            }
        """
        if not isinstance(positions, list):
            positions = [positions]

        positions = api_parse_positions(
            positions, self.trader.config[self.trader.ex.exname]['margin_rate'])

        for position in positions:
            position['exchange'] = self.trader.ex.exname

        route = f"/notification/position/danger/{self.trader.id}"
        payload = {'positions': positions}

        return await self.request('post', route, payload)

    async def notify_position_large_pl(self, positions):
        """ Notify for large pl positions
            {
                "position": {
                    "exchange": string
                    "symbol": string
                    "type": string
                    "side": string
                    "amount": float
                    "price": float
                    "timestamp": string
                    "margin": bool
                    "PL" float
                    "PL(%)" float
                }
            }
        """
        if not isinstance(positions, list):
            positions = [positions]

        positions = api_parse_positions(
            positions, self.trader.config[self.trader.ex.exname]['margin_rate'])

        for position in positions:
            position['exchange'] = self.trader.ex.exname

        route = f"/notification/position/large_pl/{self.trader.id}"
        payload = {'positions': positions}

        return await self.request('post', route, payload)

    async def notify_start(self):
        """ Notify for starting trader server """
        route = f"/notification/start/{self.trader.id}"
        payload = {'message': 'Trader server is ready.'}

        return await self.request('post', route, payload)

    async def notify_log(self, level, msg):
        """ Send logging message
            Send:
            {
                "level": string
                "message": string
            }
        """
        route = f"/notification/log/{self.trader.id}"
        payload = {'level': level, 'message': msg}

        return await self.request('post', route, payload)

    async def notify_msg(self, msg):
        """ Send any message """
        route = f"/notification/message/{self.trader.id}"
        payload = {'message': msg}

        return await self.request('post', route, payload)

    async def request(self, method, route, payload=None, header=None):
        request_method = getattr(self.session, method)
        _header = copy.deepcopy(self.default['header'])
        _payload = copy.deepcopy(self.default['payload'])

        if header:
            _header.update(header)

        if payload:
            _payload.update(payload)

        _payload = json.dumps(_payload)
        _header['x-hub-signature'] = \
            'sha1=' + gen_signature(_payload, self.secret, sha1)

        async with request_method(
            self.base_url + route,
            headers=_header,
            data=_payload) as res:

            raw = await res.text()
            content = {}

            try:
                content = json.loads(raw)
            except json.JSONDecodeError:
                logger.error(f"JSON load failed:\n{raw}")

            return content

    async def close(self):
        await self.session.close()


def gen_signature(message, secret, algorithm, digest='hex'):
    secret = bytes(secret, 'UTF-8')
    message = bytes(message, 'UTF-8')

    h = hmac.new(secret, message, algorithm)

    if digest == 'hex':
        return h.hexdigest()
    elif digest == 'base64':
        return base64.b64encode(h.digest())
    return h.digest()
