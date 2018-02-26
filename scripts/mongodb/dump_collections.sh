#!/bin/bash

tfs=(
  "1m"
)

ohlcvs=(
  "bitfinex_ohlcv_BTCUSD"
  "bitfinex_ohlcv_BCHUSD"
  "bitfinex_ohlcv_ETHUSD"
  "bitfinex_ohlcv_ETCUSD"
  "bitfinex_ohlcv_EOSUSD"
  "bitfinex_ohlcv_DASHUSD"
  "bitfinex_ohlcv_IOTAUSD"
  "bitfinex_ohlcv_LTCUSD"
  "bitfinex_ohlcv_NEOUSD"
  "bitfinex_ohlcv_OMGUSD"
  "bitfinex_ohlcv_XMRUSD"
  "bitfinex_ohlcv_XRPUSD"
  "bitfinex_ohlcv_ZECUSD"
)

trades=(
  "bitfinex_trades_BTCUSD"
  "bitfinex_trades_BCHUSD"
  "bitfinex_trades_ETHUSD"
  "bitfinex_trades_ETCUSD"
  "bitfinex_trades_EOSUSD"
  "bitfinex_trades_DASHUSD"
  "bitfinex_trades_IOTAUSD"
  "bitfinex_trades_LTCUSD"
  "bitfinex_trades_NEOUSD"
  "bitfinex_trades_OMGUSD"
  "bitfinex_trades_XMRUSD"
  "bitfinex_trades_XRPUSD"
  "bitfinex_trades_ZECUSD"
)

data_type="ohlcv"
dest="$HOME/mongo_backup/exchange/$data_type"

mkdir -p $dest

if [ $data_type = "ohlcv" ]; then

  for c in ${ohlcvs[@]}
  do
    for tf in ${tfs[@]}
    do
      coll=$c"_"$tf
      mongodump -d exchange_new -c $coll --gzip --archive="$dest/$coll.gzip"
    done
  done

elif [ $data_type = "trades" ]; then

  for c in ${trades[@]}
  do
    mongodump -d exchange_new -c $coll --gzip --archive="$dest/$coll.gzip"
  done

fi
