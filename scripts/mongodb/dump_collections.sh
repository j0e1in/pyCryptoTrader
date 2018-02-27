#!/bin/bash

db="exchange"
ex="bitfinex"
data_type=""
dest="$HOME/mongo_backup"

mkdir -p $dest

if [ $data_type = "ohlcv" ]; then
  prefix=$ex"_trades_"
  mongodump -d $db --out $dest --excludeCollectionsWithPrefix=$prefix
elif [ $data_type = "trades" ]; then
  prefix=$ex"_ohlcv_"
  mongodump -d $db --out $dest --excludeCollectionsWithPrefix=$prefix
else
  mongodump -d $db --out $dest
fi
