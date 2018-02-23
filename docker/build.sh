#/bin/bash

export IMG_TYPE=$1
export IMG_VERSION=$2

if [ -z "$IMG_TYPE" ] || [ -z "$IMG_VERSION" ]; then
  echo "Usage: ./build.sh [jessie | slim | alpine] [version]"
else
  docker build -t pycryptotrader:$IMG_VERSION-$IMG_TYPE -f Dockerfile-$IMG_TYPE ..
fi