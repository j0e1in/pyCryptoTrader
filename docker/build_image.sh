#/bin/bash

target=$1

if [ -z "$*" ]; then
  echo "Usage: build_image.sh [target: main | trade | optimize | fetch_ohlcv | fetch_trades | build_ohlcvs]"
fi

if [ $target = "all" ]; then
  docker build -t pycryptotrader ../
  docker tag pycryptotrader gcr.io/docker-reghub/pycryptotrader

  docker build -t pycryptotrader.trade ./trade
  docker build -t pycryptotrader.optimize ./optimize
  docker build -t pycryptotrader.fetch_ohlcv ./fetch_ohlcv
  docker build -t pycryptotrader.fetch_trades ./fetch_trades
  docker build -t pycryptotrader.build_ohlcvs ./build_ohlcvs
fi

if [ $target = "main" ]; then
  docker build -t pycryptotrader ../
  docker tag pycryptotrader gcr.io/docker-reghub/pycryptotrader
fi

if [ $target = "trade" ]; then
  docker build -t pycryptotrader.trade ./trade
fi

if [ $target = "optimize" ]; then
  docker build -t pycryptotrader.optimize ./optimize
fi

if [ $target = "fetch_ohlcv" ]; then
  docker build -t pycryptotrader.fetch_ohlcv ./fetch_ohlcv
fi

if [ $target = "fetch_trades" ]; then
  docker build -t pycryptotrader.fetch_trades ./fetch_trades
fi

if [ $target = "build_ohlcvs" ]; then
  docker build -t pycryptotrader.build_ohlcvs ./build_ohlcvs
fi


# export IMG_TYPE=$1
# export IMG_VERSION=$2

# if [ -z "$IMG_TYPE" ] || [ -z "$IMG_VERSION" ]; then
#   echo "Usage: ./build.sh [jessie | slim | alpine] [version]"
# else
#   docker build -t pycryptotrader:$IMG_VERSION-$IMG_TYPE -f Dockerfile-$IMG_TYPE ..
# fi

