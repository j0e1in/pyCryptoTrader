#!/bin/bash

db="exchange"
ex="bitfinex"
dest="$HOME/mongo_backup/"

mkdir -p $dest

prefix=$ex"_trades_"
mongodump -d $db --out $dest --excludeCollectionsWithPrefix=$prefix

cd $dest
mv "exchange" "ohlcvs"
zip -r -9 "ohlcvs.zip" "ohlcvs"