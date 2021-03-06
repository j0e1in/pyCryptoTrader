from argparse import RawTextHelpFormatter
from dotenv import load_dotenv

import argparse
import os
import sys

def parse_args():
    parser = argparse.ArgumentParser(formatter_class=RawTextHelpFormatter, allow_abbrev=False)

    # Analysis
    parser.add_argument('--build-ohlcvs', action='store_true', help="Execute build_ohlcv.py")
    parser.add_argument('--fetch-ohlcvs', action='store_true', help="Execute fetch_all_ohlcvs.py")
    parser.add_argument('--fetch-trades', action='store_true', help="Execute fetch_all_trades.py")
    parser.add_argument('--optimize-params', action='store_true', help="Execute optimize_params.py")
    parser.add_argument('--backtest', action='store_true', help="Execute run_backtest.py")
    parser.add_argument('--delete-vm-low-cpu', action='store_true', help="Execute delete_vm_low_cpu.py")

    # Mongodb
    parser.add_argument('--setup-mongo-container', action='store_true', help="Execute setup_mongo_container.sh")
    parser.add_argument('--create-mongo-index', action='store_true', help="Execute create_index.js")
    parser.add_argument('--create-mongo-user', action='store_true', help="Execute create_user.js")
    parser.add_argument('--drop-ohlcvs', action='store_true', help="Execute drop_ohlcvs.js")
    parser.add_argument('--drop-trades', action='store_true', help="Execute drop_ohlcvs.js")

    # Trading
    parser.add_argument('--ohlcv-stream', action='store_true', help="Execute ohlcv_stream.py")
    parser.add_argument('--trade-stream', action='store_true', help="Execute trade_stream.py")
    parser.add_argument('--start-trader', action='store_true', help="Execute start_trader.py")
    parser.add_argument('--restart-trader', action='store_true', help="Execute restart_trader.py")
    parser.add_argument('--add-trader', type=str, help="Execute manage_trader.py --add")
    parser.add_argument('--remove-trader', type=str, help="Execute manage_trader.py --rm")
    parser.add_argument('--close-position', action='store_true', help="Execute close_position.py")

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

    if argv.none:
        return

    path = argv.env if argv.env else '.env'
    load_dotenv(dotenv_path=path)

    if argv.build_ohlcvs:
        os.system(f"python scripts/analysis/build_ohlcvs.py {argv_remain}")

    elif argv.fetch_ohlcvs:
        os.system(f"python scripts/analysis/fetch_all_ohlcvs.py {argv_remain}")

    elif argv.fetch_trades:
        os.system(f"python scripts/analysis/fetch_all_trades.py {argv_remain}")

    elif argv.optimize_params:
        os.system(f"python scripts/analysis/optimize_params.py {argv_remain}")

    elif argv.backtest:
        os.system(f"python scripts/analysis/run_backtest.py {argv_remain}")

    elif argv.delete_vm_low_cpu:
        os.system(f"python scripts/system/delete_vm_low_cpu.py {argv_remain}")

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

    elif argv.ohlcv_stream:
        os.system(f"python scripts/trading/ohlcv_stream.py {argv_remain}")

    elif argv.trade_stream:
        os.system(f"python scripts/trading/trade_stream.py {argv_remain}")

    elif argv.start_trader:
        os.system(f"python scripts/trading/start_trader.py {argv_remain}")

    elif argv.restart_trader:
        os.system(f"python scripts/trading/restart_trader.py {argv_remain}")

    elif argv.add_trader:
        os.system(f"python scripts/trading/manage_trader.py --add=\"{argv.add_trader}\"")

    elif argv.remove_trader:
        os.system(f"python scripts/trading/manage_trader.py --rm=\"{argv.remove_trader}\"")

    elif argv.close_position:
        os.system(f"python scripts/trading/close_position.py {argv_remain}")

    else:
        parser.print_help(sys.stderr)

if __name__ == '__main__':
    main()