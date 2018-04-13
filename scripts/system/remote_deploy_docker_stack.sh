#!/bin/bash

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
      --pull) pull="true";;
      --cmd=*) IFS='=' read -r _ CMD <<< $3;; # split by first '='
      *) break
    esac
    shift
done

echo "Deploy $TYPE docker stack to $USERNAME@$HOST"

read -p "Press [Enter] to continue..."

# If --pull argument is specified,
# pull from docker registry instead of build from source
if [ "$pull" == "true" ]; then
  GET_IMAGE="docker pull gcr.io/docker-reghub/pyct"
else
  GET_IMAGE="docker-compose build $build_args"
fi


DEPLOY_CMD=":"
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

else # deploy trader
  STACK_NAME=crypto
  SERVICE_NAME=$STACK_NAME"_trade"
  TAIL_LOG="docker service logs -f $SERVICE_NAME"
fi


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
  \
  $DEPLOY_CMD && \
  $GET_IMAGE && \
  \
  docker stack rm $STACK_NAME && \
  echo \"wait for 10 seconds...\" && \
  sleep 10 && \
  \
  docker stack deploy -c $DOCKER_DIR/$STACK_FILE $STACK_NAME && \
  echo \"wait for 10 seconds...\" && \
  sleep 10 && \
  \
  $TAIL_LOG"

