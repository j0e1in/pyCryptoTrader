from argparse import RawTextHelpFormatter
from dotenv import load_dotenv

import argparse
import os
import sys

def parse_args():
    parser = argparse.ArgumentParser(formatter_class=RawTextHelpFormatter)

    # Analysis
    parser.add_argument('--build-ohlcvs', action='store_true', help="Execute build_ohlcv.py")
    parser.add_argument('--fetch-ohlcvs', action='store_true', help="Execute fetch_all_ohlcvs.py")
    parser.add_argument('--fetch-trades', action='store_true', help="Execute fetch_all_trades.py")
    parser.add_argument('--optimize', action='store_true', help="Execute optimize_params.py")
    parser.add_argument('--backtest', action='store_true', help="Execute run_backtest.py")

    # Mongodb
    parser.add_argument('--setup-mongo-container', action='store_true', help="Execute setup_mongo_container.sh")
    parser.add_argument('--create-mongo-index', action='store_true', help="Execute create_index.js")
    parser.add_argument('--create-mongo-user', action='store_true', help="Execute create_user.js")
    parser.add_argument('--drop-ohlcvs', action='store_true', help="Execute drop_ohlcvs.js")
    parser.add_argument('--drop-trades', action='store_true', help="Execute drop_ohlcvs.js")

    # Trading
    parser.add_argument('--start-trader', action='store_true', help="Execute start_trader.py")
    parser.add_argument('--restart-trader', action='store_true', help="Execute restart_trader.py")

    parser.add_argument('--none', action='store_true', help="Do not execute anything, this is for docker-compose")

    # Optional argument
    parser.add_argument('--env', type=str, help="Env file to load")


    argv, argv_remain = parser.parse_known_args()
    return argv, argv_remain, parser


def main():
    append_argv = []

    # Remove help arg and append later if the help arg is for the script
    # because help arg is top priority in argparse
    for arg in ['-h', '--help']:
        if arg in sys.argv and not sys.argv.index(arg) is 1:
            sys.argv.remove(arg)
            append_argv.append(arg)

    argv, argv_remain, parser = parse_args()

    argv_remain += append_argv
    argv_remain = ' '.join(argv_remain)

    if not argv_remain:
        argv_remain = ''

    if argv.env:
        load_dotenv(dotenv_path=argv.env)

    if argv.none:
        return

    elif argv.build_ohlcvs:
        os.system(f"python scripts/analysis/build_ohlcvs.py {argv_remain}")

    elif argv.fetch_ohlcvs:
        os.system(f"python scripts/analysis/fetch_all_ohlcvs.py {argv_remain}")

    elif argv.fetch_trades:
        os.system(f"python scripts/analysis/fetch_all_trades.py {argv_remain}")

    elif argv.optimize:
        os.system(f"python scripts/analysis/optimize_params.py {argv_remain}")

    elif argv.backtest:
        os.system(f"python scripts/analysis/run_backtest.py {argv_remain}")

    elif argv.setup_mongo_container:
        os.system(f"./scripts/mongodb/setup_mongo_container.sh {argv_remain}")

    elif argv.create_mongo_index:
        os.system(f"mongo {argv_remain} < scripts/mongodb/create_index.js")

    elif argv.create_mongo_user:
        os.system(f"mongo {argv_remain} < scripts/mongodb/create_user.js")

    elif argv.drop_ohlcvs:
        os.system(f"mongo {argv_remain} < scripts/mongodb/drop_ohlcvs.js")

    elif argv.drop_trades:
        os.system(f"mongo {argv_remain} < scripts/mongodb/drop_trades.js")

    elif argv.start_trader:
        os.system(f"python scripts/trading/start_trader.py {argv_remain}")

    elif argv.restart_trader:
        os.system(f"python scripts/trading/restart_trader.py {argv_remain}")

    else:
        parser.print_help(sys.stderr)

if __name__ == '__main__':
    main()