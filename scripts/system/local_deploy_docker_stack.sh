#!/bin/bash

PROJ_DIR=pyCryptoTrader
DOCKER_DIR=docker
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
    case $2 in
      --no-cache) build_args="$build_args --no-cache";;
      --pull) pull="true";;
      --cmd=*) IFS='=' read -r _ CMD <<< $2;; # split by first '='
      *) break
    esac
    shift
done

echo "Deploy $TYPE docker stack"

read -p "Press [Enter] to continue..."

if [ $pull = "true" ]; then
  GET_IMAGE="docker pull gcr.io/docker-reghub/pyct"
else
  GET_IMAGE="docker-compose build $build_args"
fi

# deploy any python app.py command
if [ $TYPE = "uni" ]; then
  export PYCT_CMD=$CMD
  source .env

  $GET_IMAGE

  docker stack rm pyct
  echo "wait for 10 seconds..."
  sleep 10

  docker stack deploy -c $DOCKER_DIR/docker-stack.yml pyct
  echo "wait for 10 seconds..."
  sleep 10

  docker service logs -f pyct_main

# deploy parameter optimization
elif [ $TYPE = 'optimize' ]; then
  source .env

  $GET_IMAGE

  docker stack rm optimize
  echo "wait for 20 seconds..."
  sleep 20

  docker stack deploy -c $DOCKER_DIR/docker-stack-$TYPE.yml optimize
  echo "wait for 10 seconds..."
  sleep 10

  docker service logs -f optimize_optimize

else
  source .env

  $GET_IMAGE

  docker stack rm crypto
  docker stack rm data
  echo "wait for 20 seconds..."
  sleep 20

  docker stack deploy -c $DOCKER_DIR/docker-stack-data-stream.yml data
  docker stack deploy -c $DOCKER_DIR/docker-stack-$TYPE.yml crypto
  echo "wait for 10 seconds..."
  sleep 10

  docker service logs -f crypto_trade
fi