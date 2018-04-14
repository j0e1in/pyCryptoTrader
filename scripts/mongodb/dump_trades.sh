#!/bin/bash

db="exchange"
ex="bitfinex"
dest="$HOME/mongo_backup/trades"

mkdir -p $dest

prefix=$ex"_ohlcv_"
mongodump -d $db --out $dest --excludeCollectionsWithPrefix=$prefix

cd $dest
mv "exchange" "trades"
zip -r -9 "trades.zip" "trades"