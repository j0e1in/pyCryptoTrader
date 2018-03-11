# pyCryptoTrader

A full program for trading cryptocurrencies automatically, including data fetching, backtesting, and trading bot.

# Usage

Use one of the options below to run a task. (only use one options at a time) Some configurations may be required, for details, please look into source code.

```bash
python app.py -h

optional arguments:
  -h, --help            show this help message and exit
  
  --build-ohlcvs        Execute build_ohlcv.py
  --fetch-ohlcvs        Execute fetch_all_ohlcvs.py
  --fetch-trades        Execute fetch_all_trades.py
  --optimize            Execute optimize_params.py
  --backtest            Execute run_backtest.py
  --create-mongo-index  Execute create_index.js
  --create-mongo-user   Execute create_user.js
  --drop-ohlcvs         Execute drop_ohlcvs.js
  --drop-trades         Execute drop_ohlcvs.js
  --start-trader        Execute start_trader.py
  --restart-trader      Execute start_trader.py with restart.py
  
  --args ARGS           Arguments to be passed to the script that are going to
                        be executed. Wrapped with ""
```

## Examples

```
# Build ohlcvs start from their most recent datetime
python app.py --build-ohlcvs

# Build ohlcvs start from first record of 1m ohlcv
python app.py --build-ohlcvs --args "--from-start"

# Fetch ohlcvs start from their most recent records to current time
python app.py --fetch-ohlcvs

# Fetch ohlcvs start from 2018/2/1 to current time
python app.py --fetch-ohlcvs --args "-s 2018/2/1"

# Fetch ohlcvs start from 2018/2/1 to 2018/3/1, end datetime must not greater then current
python app.py --fetch-ohlcvs --args "-s 2018/2/1 -e 2018/3/1"

python app.py --optimize --args "generate-params

# Read a specific pkl file that contains combinations of param set and print the total number if combinations
python app.py --optimize --args "count --prefix prefix_of_the_pkl"
```

