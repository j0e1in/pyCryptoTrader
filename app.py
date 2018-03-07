import argparse
import os


def parse_args():
    parser = argparse.ArgumentParser()

    # Analysis
    parser.add_argument('--build-ohlcvs', action='store_true', help="Execute build_ohlcv.py")
    parser.add_argument('--fetch-ohlcvs', action='store_true', help="Execute fetch_all_ohlcvs.py")
    parser.add_argument('--fetch-trades', action='store_true', help="Execute fetch_all_trades.py")
    parser.add_argument('--optimize', action='store_true', help="Execute optimize_params.py")
    parser.add_argument('--backtest', action='store_true', help="Execute run_backtest.py")

    # Mongodb
    parser.add_argument('--create-mongo-index', action='store_true', help="Execute create_index.js")
    parser.add_argument('--create-mongo-user', action='store_true', help="Execute create_user.js")
    parser.add_argument('--drop-ohlcvs', action='store_true', help="Execute drop_ohlcvs.js")
    parser.add_argument('--drop-trades', action='store_true', help="Execute drop_ohlcvs.js")

    # Trading
    parser.add_argument('--start-trader', action='store_true', help="Execute start_trader.py")
    parser.add_argument('--restart-trader', action='store_true', help="Execute start_trader.py with restart.py")

    parser.add_argument('--args', type=str, help="Arguments to be passed to the script that "\
                                                 "are going to be executed. Wrapped with \"\"")

    argv = parser.parse_args()
    return argv


def main():
    argv = parse_args()

    if argv.build_ohlcvs:
        os.system(f"python scripts/analysis/build_ohlcvs.py {argv.args}")

    elif argv.fetch_ohlcvs:
        os.system(f"python scripts/analysis/fetch_all_ohlcvs.py {argv.args}")

    elif argv.fetch_trades:
        os.system(f"python scripts/analysis/fetch_all_trades.py {argv.args}")

    elif argv.optimize:
        os.system(f"python scripts/analysis/optimize_params.py {argv.args}")

    elif argv.backtest:
        os.system(f"python scripts/analysis/run_backtest.py {argv.args}")

    elif argv.create_mongo_index:
        os.system(f"mongo {argv.args} < scripts/mongodb/create_index.js")

    elif argv.create_mongo_user:
        os.system(f"mongo {argv.args} < scripts/mongodb/create_user.js")

    elif argv.drop_ohlcvs:
        os.system(f"mongo {argv.args} < scripts/mongodb/drop_ohlcvs.js")

    elif argv.drop_trades:
        os.system(f"mongo {argv.args} < scripts/mongodb/drop_trades.js")

    elif argv.start_trader:
        os.system(f"python scripts/trading/start_trader.py {argv.args}")

    elif argv.restart_trader:
        os.system(f"python scripts/trading/restart.py scripts/trading/start_trader.py {argv.args}")


if __name__ == '__main__':
    main()