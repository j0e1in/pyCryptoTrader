from sanic import response

import asyncio
import copy
import logging
import inspect
import numpy as np
import sanic

from api.auth import AuthyManager
from db import Datastore
from utils import \
    INF, \
    dt_ms, \
    config, \
    load_json, \
    log_config

logger = logging.getLogger('pyct')


dummy_data = load_json(config['dummy_data_file'])

def customized_sanic_log_config():
    s_config = sanic.log.LOGGING_CONFIG_DEFAULTS

    s_config['formatters']['generic']['datefmt'] = \
        log_config['formatters']['pyct_colored']['datefmt']
    s_config['formatters']['generic']['format'] = \
        log_config['formatters']['pyct_colored']['format']
    s_config['formatters']['access']['datefmt'] = \
        log_config['formatters']['pyct_colored']['datefmt']
    s_config['formatters']['access']['format'] = \
        "%(asctime)s | %(levelname)s | %(request)s %(message)s %(status)d %(byte)d"

    return s_config


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

    def __init__(self, mongo, traders, custom_config=None, reset_state=False):
        self.ds = Datastore.create('apiserver')

        if reset_state:
            self.ds.clear()

        self.mongo = mongo
        self.authy = AuthyManager(mongo)
        self.log_level = self.ds.get('log_level', {})

        _config = custom_config if custom_config else config
        self._config = self.ds.get('_config', _config)
        self.config = self._config['apiserver']

        self.app.traders = traders
        self.app.server = self
        self.app.config.KEEP_ALIVE = config['apiserver']['keep_alive']
        self.app.config.KEEP_ALIVE_TIMEOUT = config['apiserver']['keep_alive_timeout']
        self.app.config.REQUEST_TIMEOUT = config['apiserver']['request_timeout']
        self.app.config.RESPONSE_TIMEOUT = config['apiserver']['response_timeout']

    async def run(self, host='0.0.0.0', port=8000, enable_ssl=False, **kwargs):
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

        with_ssl = 'with' if enable_ssl else 'without'
        logger.info(f"Starting API server {with_ssl} SSL")

        start_server = self.app.create_server(host=host, port=port, ssl=context, **kwargs)
        await asyncio.gather(start_server)

    @app.route('/register/account', methods=['POST'])
    async def register_uid(req):
        payload = req.json
        if not payload \
        or 'uid' not in payload \
        or 'exchange' not in payload \
        or 'exchange_username' not in payload \
        or 'auth_level' not in payload:
            return response.json({
                'error': "Payload should contain fields "
                         "`uid`, `exchange`, `exchange_username`, `auth_level`"
            })

        uid = payload['uid']
        ex = payload['exchange']
        ex_user = payload['exchange_username']
        auth_level = payload['auth_level']

        if await req.app.server.uid_exist(uid, ex):
            return response.json({'error': "Account already exists"})

        # Ask owner to confirm request, if one is already using that exchange account
        owner_uid = await req.app.server.ex_account_exist(ex, ex_user)
        if owner_uid:
            msg = f"Create user on your {ex} account?\n{uid}-{ex_user}-{auth_level}"
            accept, res = await req.app.server.send_2fa_request(owner_uid, msg)

            if not accept:
                return res

        mongo = req.app.server.mongo
        coll = mongo.get_collection(mongo.config['dbname_api'], 'account')
        coll.insert({
            'uid': uid,
            'ex': ex,
            'ex_username': ex_user,
            'auth_level': auth_level
        })
        logger.info(f"Registered account: uid={uid}, ex={ex}, username={ex_user}, auth_level={auth_level}")

        return response.json({'ok': True})

    @app.route('/register/authy', methods=['POST'])
    async def authy_create_user(req):
        """ Add authy user to database, and authy will send 2FA to their account. """
        payload = req.json
        if not payload \
        or 'uid' not in payload \
        or 'email' not in payload \
        or 'phone' not in payload \
        or 'country_code' not in payload:
            return response.json({
                'error': "Payload should contain fields "
                         "`uid`, `email`, `phone` and `country_code`"
            })

        succ, res = await req.app.server.authy.create_user(
            payload['uid'],
            payload['email'],
            payload['phone'],
            payload['country_code']
        )
        logger.info(f"Registered authy: "
            f"uid={payload['uid']}, "
            f"email={payload['email']}, "
            f"phone={payload['phone']}, "
            f"country_code={payload['country_code']}")

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
        if not await req.app.server.verified_access(uid, ex, inspect.stack()[0][3]):
            return response.json({'error': 'Unauthorized'}, status=401)

        if not req.app.server.trader_active(req.app.traders, uid, ex):
            return response.json({'error': f'Trader [{uid}-{ex}] has not been activated'})

        trader = req.app.traders[f"{uid}-{ex}"]

        if not trader.ex.is_ready():
            return response.json({'error': 'Not ready'})

        if uid == "1492068960851477":
            msg = f"Query account info"
            accept, res = await req.app.server.send_2fa_request(uid, msg)

        if not accept:
            return res

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
        if not await req.app.server.verified_access(uid, ex, inspect.stack()[0][3]):
            return response.json({'error': 'Unauthorized'}, status=401)

        if not req.app.server.trader_active(req.app.traders, uid, ex):
            return response.json({'error': f'Trader [{uid}-{ex}] has not been activated'})

        trader = req.app.traders[f"{uid}-{ex}"]

        if not trader.ex.is_ready():
            return response.json({'error': 'Not ready'})

        if uid == "1492068960851477":
            msg = f"Query account summary"
            accept, res = await req.app.server.send_2fa_request(uid, msg)

        if not accept:
            return res

        summ = copy.deepcopy(await trader.get_summary())
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
        if 'dummy-data' in req.headers \
        and req.headers['dummy-data'] == 'true':
            return response.json(dummy_data['active_orders'])

        if not await req.app.server.verified_access(uid, ex, inspect.stack()[0][3]):
            return response.json({'error': 'Unauthorized'}, status=401)

        if not req.app.server.trader_active(req.app.traders, uid, ex):
            return response.json({'error': f'Trader [{uid}-{ex}] has not been activated'})

        trader = req.app.traders[f"{uid}-{ex}"]

        if uid == "1492068960851477":
            msg = f"Query active orders"
            accept, res = await req.app.server.send_2fa_request(uid, msg)

        if not accept:
            return res

        orders = await trader.ex.fetch_open_orders()
        orders = api_parse_orders(orders)

        return response.json({'orders': orders })

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
        if 'dummy-data' in req.headers \
        and req.headers['dummy-data'] == 'true':
            return response.json(dummy_data['active_positions'])

        if not await req.app.server.verified_access(uid, ex, inspect.stack()[0][3]):
            return response.json({'error': 'Unauthorized'}, status=401)

        if not req.app.server.trader_active(req.app.traders, uid, ex):
            return response.json({'error': f'Trader [{uid}-{ex}] has not been activated'})

        trader = req.app.traders[f"{uid}-{ex}"]

        if uid == "1492068960851477":
            msg = f"Query active positions"
            accept, res = await req.app.server.send_2fa_request(uid, msg)

        if not accept:
            return res

        positions = await trader.ex.fetch_positions()
        positions = api_parse_positions(
            positions, trader.config[trader.ex.exname]['margin_rate'])

        return response.json({'positions': positions })

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
        if not await req.app.server.verified_access(uid, ex, inspect.stack()[0][3]):
            return response.json({'error': 'Unauthorized'}, status=401)

        if not req.app.server.trader_active(req.app.traders, uid, ex):
            return response.json({'error': f'Trader [{uid}-{ex}] has not been activated'})

        trader = req.app.traders[f"{uid}-{ex}"]

        if not trader.ex.is_ready():
            return response.json({'error': 'Not ready'})

        sigs = trader.strategy.signals
        if not sigs:
            return response.json({'error': 'Not ready'})

        if uid == "1492068960851477":
            msg = f"Query signals"
            accept, res = await req.app.server.send_2fa_request(uid, msg)

        if not accept:
            return res

        signals = {'signals': {}}

        for market in sigs:
            signals['signals'][market] = []
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

                signals['signals'][market].append({
                    'timestamp': dt_ms(dt),
                    'signal': action
                })

        return response.json(signals)

    @app.route('/ping', methods=['GET'])
    async def ping(req):
        return response.json({'ok': True })

    ############################
    ##       2FA Required     ##
    ############################

    @app.route('/notification/log_level/<uid:string>', methods=['POST'])
    async def change_log_level(req, uid):
        if not await req.app.server.verified_access(uid, '', inspect.stack()[0][3]):
            return response.json({'error': 'Unauthorized'}, status=401)

        payload = req.json
        if not payload or 'level' not in payload:
            return response.json({
                'error': "Payload should contain field `level` "
                         "with one of values: info | debug | warn | error"
            })

        if not req.app.server.trader_active(req.app.traders, uid):
            return response.json({'error': f'Trader [{uid}] has not been activated'})

        msg = f"Set log level to {payload['level']}"
        accept, res = await req.app.server.send_2fa_request(uid, msg)

        if not accept:
            return res

        req.app.server.log_level[uid] = payload['level']
        return response.json({'ok': True})

    @app.route('/notification/large_pl/<uid:string>', methods=['POST'])
    async def change_large_pl_threshold(req, uid):
        if not await req.app.server.verified_access(uid, '', inspect.stack()[0][3]):
            return response.json({'error': 'Unauthorized'}, status=401)

        payload = req.json
        if not payload or 'PL(%)' not in payload:
            return response.json({
                'error': "Payload should contain field `PL(%)`"
            })

        if not req.app.server.trader_active(req.app.traders, uid):
            return response.json({'error': f'Trader [{uid}] has not been activated'})

        for ue in req.app.traders:
            if ue.startswith(uid):
                trader = req.app.traders[ue]

                msg = f"Set [{ue}] large PL threshold to {payload['PL(%)']}"
                accept, res = await req.app.server.send_2fa_request(uid, msg)

                if not accept:
                    return res

                trader._config['apiclient']['large_pl_threshold'] = payload['PL(%)']

        return response.json({'ok': True})

    @app.route('/trading/max_fund/<uid:string>', methods=['POST'])
    async def change_max_fund(req, uid):
        if not await req.app.server.verified_access(uid, '', inspect.stack()[0][3]):
            return response.json({'error': 'Unauthorized'}, status=401)

        payload = req.json
        if not payload or 'fund' not in payload:
            return response.json({
                'error': "Payload should contain field `fund` with a float value"
            })

        if not req.app.server.trader_active(req.app.traders, uid):
            return response.json({'error': f'Trader [{uid}] has not been activated'})

        for ue in req.app.traders:
            if ue.startswith(uid):
                trader = req.app.traders[ue]

                msg = f"Change max fund to ${payload['fund']}"
                accept, res = await req.app.server.send_2fa_request(uid, msg)

                if not accept:
                    return res

                trader.max_fund = payload['fund']
                logger.debug(f'Set [{ue}] max fund to {trader.max_fund}')

        return response.json({'ok': True})

    @app.route('/trading/markets/enable/<uid:string>/<ex:string>', methods=['POST'])
    async def enable_markets(req, uid, ex):
        if not await req.app.server.verified_access(uid, ex, inspect.stack()[0][3]):
            return response.json({'error': 'Unauthorized'}, status=401)

        payload = req.json
        if not payload or 'markets' not in payload or not isinstance(payload['markets'], list):
            return response.json({
                'error': "Payload should contain field `markets` with a list of strings"
            })

        if not req.app.server.trader_active(req.app.traders, uid, ex):
            return response.json({'error': f'Trader [{uid}-{ex}] has not been activated'})

        trader = req.app.traders[f"{uid}-{ex}"]

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
            return response.json({'ok': True })

    @app.route('/trading/markets/disable/<uid:string>/<ex:string>', methods=['POST'])
    async def disable_markets(req, uid, ex):
        if not await req.app.server.verified_access(uid, ex, inspect.stack()[0][3]):
            return response.json({'error': 'Unauthorized'}, status=401)

        payload = req.json
        if not payload or 'markets' not in payload or not isinstance(payload['markets'], list):
            return response.json({
                'error': "Payload should contain field `markets` with a list of strings"
            })

        if not req.app.server.trader_active(req.app.traders, uid, ex):
            return response.json({'error': f'Trader [{uid}-{ex}] has not been activated'})

        trader = req.app.traders[f"{uid}-{ex}"]

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
        if not await req.app.server.verified_access(uid, '', inspect.stack()[0][3]):
            return response.json({'error': 'Unauthorized'}, status=401)

        if not req.app.server.trader_active(req.app.traders, uid):
            return response.json({'error': f'Trader [{uid}] has not been activated'})

        for ue in req.app.traders:
            if ue.startswith(uid):
                trader = req.app.traders[ue]

                msg = "Enable trading"
                accept, res = await req.app.server.send_2fa_request(uid, msg)

                if not accept:
                    return res

                trader.enable_trading = True
                logger.info(f"Trading enabled")

        return response.json({'ok': True })

    @app.route('/trading/disable/<uid:string>', methods=['POST'])
    async def disable_trading(req, uid):
        if not await req.app.server.verified_access(uid, '', inspect.stack()[0][3]):
            return response.json({'error': 'Unauthorized'}, status=401)

        if not req.app.server.trader_active(req.app.traders, uid):
            return response.json({'error': f'Trader [{uid}] has not been activated'})

        for ue in req.app.traders:
            if ue.startswith(uid):
                trader = req.app.traders[ue]

                msg = "Disable trading"
                accept, res = await req.app.server.send_2fa_request(uid, msg)

                if not accept:
                    return res

                trader.enable_trading = False
                logger.info(f"Trading disabled")

        return response.json({'ok': True })

    ###########################
    ##         2FA End       ##
    ###########################

    async def verified_access(self, uid, ex, func):
        auth_level = str(await self.get_auth_level(uid, ex))

        if auth_level == '0':
            return False

        denied = self.config['auth_level'][auth_level]
        if func in denied:
            return False
        else:
            return True

    async def send_2fa_request(self, uid, msg):
        # Convert uid to authyid
        authyid = await self.authy.get_authyid(uid)

        # and check if the authyid is already existed
        if not authyid \
        or not await self.authy.user_exist(authyid):
            return False, response.json({'error': f'Authy user does not exist.'})

        res, status = await self.authy.one_touch(authyid, msg)
        if not res:
            return False, response.json(
                {'error': f'2FA request {status}'})
        else:
            return True, ''

    async def uid_exist(self, uid, ex):
        coll = self.mongo.get_collection(self.mongo.config['dbname_api'], 'account')
        res = await coll.find_one({'uid': uid, 'ex': ex})
        return True if res else False

    async def ex_account_exist(self, ex, ex_user):
        coll = self.mongo.get_collection(self.mongo.config['dbname_api'], 'account')
        res = await coll.find_one({'ex': ex, 'ex_user': ex_user,'auth_level': 1})
        return res['uid'] if res else ''

    async def get_auth_level(self, uid, ex):
        coll = self.mongo.get_collection(self.mongo.config['dbname_api'], 'account')

        if ex:
            res = await coll.find_one({'uid': uid, 'ex': ex})
        else:
            # if ex is not specified, use highest level
            res = await coll.find({'uid': uid}) \
                .sort([('auth_level', 1)]) \
                .limit(1) \
                .to_list(length=INF)
            res = res[0] if res else []

        if res:
            return res['auth_level']
        else:
            return 0

    def trader_active(self, traders, uid, ex=None):
        if ex:
            return f"{uid}-{ex}" in traders
        else:
            for ue in traders:
                if ue.startswith(uid):
                    return True
        return False


def api_parse_orders(orders):
    if not orders:
        return orders

    orders = copy.deepcopy(orders)

    if not isinstance(orders, list):
        orders = [orders]

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

    positions = copy.deepcopy(positions)

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
