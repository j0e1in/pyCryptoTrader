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
      --reset) export RESET_STATE=--reset;;
      --follow | -f) follow_log="-f";; # Enable follow in TAIL_LOG
      ## stack name
      --name=*) IFS='=' read -r _ STACK_NAME <<< $2;;
      ## symbols to optimize
      --symbol=*) IFS='=' read -r _ SYMBOLS <<< $2;; # split by first '='
      ## cmd to execute for the general docker-compose file
      --cmd=*) IFS='=' read -r _ CMD <<< $2;; # split by first '='
      *) break
    esac
    shift
done

# If --pull argument is specified,
# pull from docker registry instead of build from source
if [ "$pull" == "true" ]; then
  IMG_ACTION=pulling
  GET_IMAGE="docker pull gcr.io/docker-reghub/pyct"
else
  IMG_ACTION=building
  GET_IMAGE="docker-compose build $build_args"
fi


echo -e "\n>>>  Deploy $TYPE docker stack by $IMG_ACTION image  <<<\n"
# read -p "Press [Enter] to continue..."


DEPLOY_CMD=":"
TAIL_LOG=":"
STACK_FILE=docker-stack-$TYPE.yml

# deploy any python app.py command
if [ "$TYPE" == 'uni' ]; then
  if [ -z $STACK_NAME ]; then
    STACK_NAME=pyct
  fi
  export PYCT_CMD="$CMD"
  SERVICE_NAME=$STACK_NAME"_uni"
  TAIL_LOG="docker service logs $follow_log $SERVICE_NAME"

# deploy parameter optimization
elif [ "$TYPE" == 'optimize' ]; then
  if [ -z $STACK_NAME ]; then
    STACK_NAME=optimize
  fi
  SERVICE_NAME=$STACK_NAME"_optimize"
  TAIL_LOG="docker service logs $follow_log $SERVICE_NAME"

elif [ "$TYPE" == 'db' ]; then
  if [ -z $STACK_NAME ]; then
    STACK_NAME=db
  fi

elif [ "$TYPE" == 'ohlcv' ]; then
  if [ -z $STACK_NAME ]; then
    STACK_NAME=ohlcv
  fi
  SERVICE_NAME=$STACK_NAME"_ohlcv"
  TAIL_LOG="docker service logs $follow_log $SERVICE_NAME"

elif [ "$TYPE" == 'trade' ]; then
  if [ -z $STACK_NAME ]; then
    STACK_NAME=trade
  fi
  SERVICE_NAME=$STACK_NAME"_trade"
  TAIL_LOG="docker service logs $follow_log $SERVICE_NAME"

else # deploy trader
  if [ -z $STACK_NAME ]; then
    STACK_NAME=crypto
  fi
  SERVICE_NAME=$STACK_NAME"_trader"
  TAIL_LOG="docker service logs $follow_log $SERVICE_NAME"
fi

# Actually executing commands
# Authorize access permission to gcr container registry
REGHUB_KEYFILE=private/docker-reghub-0065a93a0ed4.json
gcloud auth activate-service-account --key-file $REGHUB_KEYFILE
echo -e 'y\n' | gcloud auth configure-docker

source .env
if [ $SYMBOLS ]; then
  export OPTIMIZE_SYMBOLS=$SYMBOLS
fi

$GET_IMAGE

mkdir -p ../log

docker stack rm $STACK_NAME
echo "wait for 20 seconds..."
sleep 20

docker stack deploy -c $DOCKER_DIR/$STACK_FILE $STACK_NAME
echo "wait for 20 seconds..."
sleep 20

$TAIL_LOG
