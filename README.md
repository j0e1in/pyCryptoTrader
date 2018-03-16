# pyCryptoTrader

A full-package program for trading cryptocurrencies automatically, including data fetching, back-testing, and automatic trading.

# Requirements

- Ubuntu 16.04 (Recommended)
- Docker 17.12+
- Mongo 3.6+
- GCP SDK (gcloud)

**Note**: A Ubuntu 16.04 server setup script is available, just execute

`$ ./scripts/system/dev_server_setup.sh`

# Setup

1. Setup mongo container: restore mongodb, create network and volume, and then start container in auth mode.

```sh
$ ./scripts/mongodb/setup_mongo_container.sh
```

# Usage (without docker)

- Use one of the options below to run a task. 
- Use only one option at a time. 


- Add `-h` or `--help` after a task argument to print available arguments for the task.

```sh
python app.py --help
optional arguments:
  -h, --help            show this help message and exit
  --build-ohlcvs        Execute build_ohlcv.py
  --fetch-ohlcvs        Execute fetch_all_ohlcvs.py
  --fetch-trades        Execute fetch_all_trades.py
  --optimize            Execute optimize_params.py
  --backtest            Execute run_backtest.py
  --setup-mongo-container
                        Execute setup_mongo_container.sh
  --create-mongo-index  Execute create_index.js
  --create-mongo-user   Execute create_user.js
  --drop-ohlcvs         Execute drop_ohlcvs.js
  --drop-trades         Execute drop_ohlcvs.js
  --start-trader        Execute start_trader.py
  --restart-trader      Execute restart_trader.py
```

## Examples (without docker)

```sh
# Build ohlcvs start from their most recent datetime
python app.py --build-ohlcvs

# Build ohlcvs start from first record of 1m ohlcv
python app.py --build-ohlcvs --from-start

# Fetch ohlcvs start from their most recent records to current time
python app.py --fetch-ohlcvs

# Fetch ohlcvs and do not replace existing ohlcvs
python app.py --fetch-ohlcvs --no-upsert
```

# Usage (with docker)

```sh

```

# Example (with docker)

```sh

```

# 