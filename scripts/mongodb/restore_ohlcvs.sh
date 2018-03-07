#!/bin/bash

src_db="exchange"
target_db="exchange"
src_dir="$HOME/mongo_backup"
# regex="*_ohlcv_*"

cd $src_dir
unzip ohlcvs.zip

# mongorestore --dir=$src_dir --nsInclude=$regex --nsFrom "${src_db}.*" --nsTo "${target_db}.*"
mongorestore -d $target_db $src_dir"/ohlcvs/" # --nsInclude=$regex

rm -rf $src_dir"/ohlcvs/"