#/bin/bash

target=$1

if [ -z "$*" ]; then
  echo "Usage: build_image.sh [target: main | trade | optimize | fetch_ohlcv | fetch_trades | build_ohlcvs]"
fi

if [ $target = "all" ]; then
  docker build -t pyct ../
  docker tag pyct gcr.io/docker-reghub/pyct

  docker build -t pyct_trade ./trade
  docker build -t pyct_optimize ./optimize
  docker build -t pyct_fetch_ohlcv ./fetch_ohlcv
  docker build -t pyct_fetch_trades ./fetch_trades
  docker build -t pyct_build_ohlcvs ./build_ohlcvs
fi

if [ $target = "main" ]; then
  docker build -t pyct ../
  docker tag pyct gcr.io/docker-reghub/pyct
fi

if [ $target = "trade" ]; then
  docker build -t pyct_trade ./trade
fi

if [ $target = "optimize" ]; then
  docker build -t pyct_optimize ./optimize
fi

if [ $target = "fetch_ohlcv" ]; then
  docker build -t pyct_fetch_ohlcv ./fetch_ohlcv
fi

if [ $target = "fetch_trades" ]; then
  docker build -t pyct_fetch_trades ./fetch_trades
fi

if [ $target = "build_ohlcvs" ]; then
  docker build -t pyct_build_ohlcvs ./build_ohlcvs
fi


# export IMG_TYPE=$1
# export IMG_VERSION=$2

# if [ -z "$IMG_TYPE" ] || [ -z "$IMG_VERSION" ]; then
#   echo "Usage: ./build.sh [jessie | slim | alpine] [version]"
# else
#   docker build -t pyct:$IMG_VERSION-$IMG_TYPE -f Dockerfile-$IMG_TYPE ..
# fi

