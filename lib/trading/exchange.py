from utils import combine, Timer


class EX():
""" Unifiied exchange interface for trader. """

    def __init__(self, db, apikey=None, secret=None):
        self.db = db
        self.apikey = apikey
        self.secret = secret

    def auth(self):
        return True if self.apikey and self.secret else False

    def init_ccxt_exchange(exchange_id):
    """ Return an initialized ccxt API instance. """
        options = combine({
            'rateLimit': config['constants']['rate_limit'],
            'enableRateLimit': True
        }, get_keys()[exchange_id])

        exchange = getattr(ccxt, exchange_id)(options)
        return exchange

    def is_ready(self):
        pass

    async def start(self)
        pass

    async def _start_ohlcv_stream(self):
        pass

    async def _start_trade_stream(self):
        pass

    async def _start_ticker_stream(self):
        pass

    async def _start_orderbook_stream(self):
        pass

    #####################
    # AUTHENTICATED API #
    #####################


    async def _send_ccxt_request(self, func, *args, **kwargs):
        succ = False
        while not succ:
            try:
                res = await func(*args, **kwargs)

            except (ccxt.AuthenticationError,
                    ccxt.ExchangeNotAvailable,
                    ccxt.RequestTimeout,
                    ccxt.ExchangeError,
                    ccxt.DDoSProtection) as error:

                if is_empty_response(error): # finished fetching all ohlcv
                    break
                elif isinstance(error, ccxt.ExchangeError):
                    raise error

                logger.info(f'|{type(error).__name__}| retrying in {wait} seconds...')
                await asyncio.sleep(wait)

            else:
                succ = True



def is_empty_response(err):
    return True if 'empty response' in str(err) else False

