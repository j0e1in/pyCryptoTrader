#!/bin/bash

# Usage:
#   ./scripts/system/remote_deploy_docker_stack.sh [user]@[host] [data | db | dev | test | test-trading | production | optimize]
#

PROJ_DIR=pyCryptoTrader
DOCKER_DIR=docker
CUR_DIR=$(pwd)

# Check if current path ends with project name
if [[ "$CUR_DIR" != */$PROJ_DIR ]]; then
  echo "ERROR: Please run this script at project root."
  exit 1
fi

REMOTE=$1
TYPE=$2

# Split remote by '@', into an array (-a)
IFS='@' read -r -a REMOTE <<< $REMOTE

USERNAME=${REMOTE[0]}
HOST=${REMOTE[1]}

if [ -z $USERNAME ] | [ -z $HOST ] | [ -z $TYPE ]; then
  echo "Usage: remote_deploy_docker_stack.sh [username]@[host] [type] [--no-cache] [--cmd='...']"
  exit 1
fi

# Add custom arguments to commands ran in this script
build_args=""
pull=""

# Examine arguments after the second
while :; do
    case $3 in
      --no-cache) build_args="$build_args --no-cache";;
      --pull) pull="true";; # pull image instead of building it locally
      --reset) reset_state="true";; # clear redis data
      --follow | -f) follow_log="-f";; # Enable follow in TAIL_LOG

      # Following arguments should be placed at last
      ## symbols to optimize
      --symbol=*) IFS='=' read -r _ SYMBOLS <<< $3;; # split by first '='
      ## cmd to execute for the general docker-compose file
      --cmd=*) IFS='=' read -r _ CMD <<< $3;; # split by first '='
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

if [ "$reset_state" == "true" ]; then
  RESET_STATE="export RESET_STATE=--reset"
else
  RESET_STATE=":"
fi


echo -e "\n>>>  Deploy $TYPE docker stack to $USERNAME@$HOST by $IMG_ACTION image  <<<\n"
# read -p "Press [Enter] to continue..."


DEPLOY_CMD=":"
TAIL_LOG=":"
STACK_FILE=docker-stack-$TYPE.yml

# deploy any python app.py command
if [ "$TYPE" == 'uni' ]; then
  DEPLOY_CMD="export PYCT_CMD=\"$CMD\""
  STACK_NAME=pyct
  SERVICE_NAME=$STACK_NAME"_main"
  TAIL_LOG="docker service logs $follow_log $SERVICE_NAME"

# deploy parameter optimization
elif [ "$TYPE" == 'optimize' ]; then
  STACK_NAME=optimize
  SERVICE_NAME=$STACK_NAME"_optimize"
  TAIL_LOG="docker service logs $follow_log $SERVICE_NAME"

elif [ "$TYPE" == 'db' ]; then
  STACK_NAME=db

elif [ "$TYPE" == 'data' ]; then
  STACK_NAME=data
  SERVICE_NAME=$STACK_NAME"_ohlcv"
  TAIL_LOG="docker service logs $follow_log $SERVICE_NAME"

else # deploy trader
  STACK_NAME=crypto
  SERVICE_NAME=$STACK_NAME"_trade"
  TAIL_LOG="docker service logs $follow_log $SERVICE_NAME"
fi

REGHUB_KEYFILE=private/docker-reghub-0065a93a0ed4.json

# Actually executing commands
# Zip and upload source code
cd ../
rm -rf $PROJ_DIR.zip
zip -9 -qr --exclude=*.git* $PROJ_DIR.zip $PROJ_DIR
echo 'Uploading source...'
scp $PROJ_DIR.zip $USERNAME@$HOST:~/

ssh $USERNAME@$HOST \
  "PROJ_DIR=pyCryptoTrader && \
  rm -rf $PROJ_DIR && \
  unzip -q $PROJ_DIR.zip && \
  cd $PROJ_DIR && \
  source .env && \
  if [ $SYMBOLS ]; then
    export OPTIMIZE_SYMBOLS=$SYMBOLS
  fi
  \
  # Authorize access permission to gcr container registry
  gcloud auth activate-service-account --key-file $REGHUB_KEYFILE
  echo -e 'y\n' | gcloud auth configure-docker
  \
  $DEPLOY_CMD && \
  $RESET_STATE && \
  $GET_IMAGE && \
  \
  mkdir -p ../log && \
  \
  docker stack rm $STACK_NAME && \
  echo \"wait for 20 seconds...\" && \
  sleep 20 && \
  \
  docker stack deploy -c $DOCKER_DIR/$STACK_FILE $STACK_NAME && \
  echo \"wait for 20 seconds...\" && \
  sleep 20 && \
  \
  $TAIL_LOG"

exit 0