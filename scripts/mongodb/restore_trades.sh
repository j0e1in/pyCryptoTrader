#!/bin/bash

src_db="exchange"
target_db="exchange"
src_dir="$HOME/mongo_backup"
# regex="*_trades_*"

cd $src_dir
unzip trades.zip

# mongorestore --dir=$src_dir --nsInclude=$regex --nsFrom "${src_db}.*" --nsTo "${target_db}.*"
mongorestore -d $target_db $src_dir"/trades/" # --nsInclude=$regex

rm -rf $src_dir"/trades/"