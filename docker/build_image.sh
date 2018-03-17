#/bin/bash

version=$1

docker build -t pyct ../
docker tag pyct gcr.io/docker-reghub/pyct

# export IMG_TYPE=$1
# export IMG_VERSION=$2

# if [ -z "$IMG_TYPE" ] || [ -z "$IMG_VERSION" ]; then
#   echo "Usage: ./build.sh [jessie | slim | alpine] [version]"
# else
#   docker build -t pyct:$IMG_VERSION-$IMG_TYPE -f Dockerfile-$IMG_TYPE ..
# fi

