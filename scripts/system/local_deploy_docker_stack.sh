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

if [ "$pull" == "true" ]; then
  GET_IMAGE="docker pull gcr.io/docker-reghub/pyct"
else
  GET_IMAGE="docker-compose build $build_args"
fi

DEPLOY_CMD=":"
TAIL_LOG=":"
STACK_FILE=docker-stack-$TYPE.yml

# deploy any python app.py command
if [ "$TYPE" == 'uni' ]; then
  DEPLOY_CMD="export PYCT_CMD=\"$CMD\""
  STACK_NAME=crypto
  SERVICE_NAME=$STACK_NAME"_main"
  TAIL_LOG="docker service logs -f $SERVICE_NAME"

# deploy parameter optimization
elif [ "$TYPE" == 'optimize' ]; then
  STACK_NAME=optimize
  SERVICE_NAME=$STACK_NAME"_optimize"
  TAIL_LOG="docker service logs -f $SERVICE_NAME"

elif [ "$TYPE" == 'db' ]; then
  STACK_NAME=db

elif [ "$TYPE" == 'data' ]; then
  STACK_NAME=ohlcv
  SERVICE_NAME=$STACK_NAME"_ohlcv"
  TAIL_LOG="docker service logs -f $SERVICE_NAME"

else # deploy trader
  STACK_NAME=crypto
  SERVICE_NAME=$STACK_NAME"_trade"
  TAIL_LOG="docker service logs -f $SERVICE_NAME"
fi

# Actually executing commands
# Authorize access permission to gcr container registry
REGHUB_KEYFILE=private/docker-reghub-0065a93a0ed4.json
gcloud auth activate-service-account --key-file $REGHUB_KEYFILE
gcloud auth configure-docker

source .env

$DEPLOY_CMD
$GET_IMAGE

docker stack rm $STACK_NAME
echo "wait for 20 seconds..."
sleep 20

docker stack deploy -c $DOCKER_DIR/$STACK_FILE $STACK_NAME
echo "wait for 10 seconds..."
sleep 10

$TAIL_LOG
