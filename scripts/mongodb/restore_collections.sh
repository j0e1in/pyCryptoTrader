#!/bin/bash

src_db="exchange"
target_db="exchange"
src_dir="$HOME/mongo_backup/$src_db/"

regex="*_ohlcv_*"

# mongorestore --dir=$src_dir --nsInclude=$regex --nsFrom "${src_db}.*" --nsTo "${target_db}.*"
mongorestore -d $target_db $src_dir #--nsInclude=$regex