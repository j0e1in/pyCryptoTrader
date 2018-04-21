from setup import run

from datetime import datetime

import asyncio
import logging

from api import APIServer
from db import EXMongo, Datastore
from trading.trader import SingleEXTrader, TraderManager
from utils import config, load_env


timestr = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
log_file = f"trader/start_trader_{config['uid']}_{timestr}.log"

logger = logging.getLogger('pyct')


def parse_args():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='0.0.0.0', help='Server IP')
    parser.add_argument('--port', type=int, default=8000, help='Server port')
    parser.add_argument('--log', action='store_true', help='Enable trader logging')
    parser.add_argument('--log-signal', action='store_true', help='Enable periodic indicator signal logging')
    parser.add_argument('--enable-api', action='store_true', help='Enable API server for clients to request data')
    parser.add_argument('--enable-ohlcv-stream', action='store_true', help='Enable fetching ohlcvs')
    parser.add_argument('--ssl', action='store_true', help='Enable SSL, only works if API sever is enabled')
    parser.add_argument('--mongo-ssl', action='store_true', help='Add SSL files to mongo client')
    parser.add_argument('--disable-trading', action='store_true', help='Disable creating orders')
    parser.add_argument('--disable-notification', action='store_true', help='Disable sending notification to clients')
    parser.add_argument('--redis-host', type=str, help='Specify redis host')
    parser.add_argument('--mongo-host', type=str, help="Specify mongodb host,\n"
                                                       "eg. localhost (host connect to mongo on host)\n"
                                                       "    mongo (container connect to mongo container)\n"
                                                       "    172.18.0.2 (host connect to mongo container)\n")
    parser.add_argument('--reset', action='store_true', help='Reset app state, start fresh')
    parser.add_argument('--manager', action='store_true', help='Start traders with a manager')
    argv = parser.parse_args()

    return argv


async def main():
    argv = parse_args()

    load_env()

    mongo_host = argv.mongo_host or None
    redis_host = argv.redis_host or None

    mongo = EXMongo(host=mongo_host, ssl=argv.mongo_ssl)
    Datastore.update_redis(host=redis_host)

    if not argv.manager:
        if argv.enable_api:
            raise RuntimeError(f"API server requires a trader manager, "
                               f"add `--manager` when starting trader")
        uid = '1492068960851477'
        ex = 'bitfinex'
        trader = SingleEXTrader(mongo, ex, 'pattern',
            uid=uid,
            log=argv.log,
            log_sig=argv.log_signal,
            disable_trading=argv.disable_trading,
            disable_ohlcv_stream=(not argv.enable_ohlcv_stream),
            disable_notification=argv.disable_notification,
            reset_state=argv.reset)

        await trader.start()
        await trader.ex.ex.close()

    else:
        exs = ['bitfinex'] if argv.enable_api else []

        await TraderManager(mongo,
            enable_api=argv.enable_api,

            trader_args=(mongo,),
            trader_kwargs=dict(
                strategy='pattern',
                log=argv.log,
                log_sig=argv.log_signal,
                disable_trading=argv.disable_trading,
                disable_ohlcv_stream=(not argv.enable_ohlcv_stream),
                disable_notification=argv.disable_notification,
                reset_state=argv.reset),

            apiserver_args=(),
            apiserver_kwargs=dict(
                reset_state=argv.reset),

            apiserver_run_args=(),
            apiserver_run_kwargs=dict(
                access_log=True,
                enable_ssl=argv.ssl)
        ).start(exs)


if __name__ == '__main__':
    run(main, log_file=log_file)
