#!/bin/bash

PROJ_DIR=pyCryptoTrader
CUR_DIR=$(pwd)

if [[ "$CUR_DIR" != */$PROJ_DIR ]]; then
  echo "ERROR: Please run this script at project root."
  exit 1
fi

TYPE=$1

if [ -z $TYPE ]; then
  echo "Usage: local_deploy_docker_stack.sh [type] [--no-cache]"
  exit 1
fi

# Add custom arguments to commands ran in this script
build_args=""

while :; do
    case $3 in
      --no-cache) build_args="$build_args --no-cache";;
      *) break
    esac
    shift
done

echo "Deploy $TYPE docker stack"

read -p "Press [Enter] to continue..."

docker-compose build

docker stack rm crypto
docker stack rm data
echo \"wait for 20 seconds...\"
sleep 20

docker stack deploy -c docker-stack-data-stream.yml data
docker stack deploy -c docker-stack-$TYPE.yml crypto
echo \"wait for 10 seconds...\"
sleep 10

docker service logs -f crypto_trade