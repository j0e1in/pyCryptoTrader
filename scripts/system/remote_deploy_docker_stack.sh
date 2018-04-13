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
PULL=""

# Examine arguments after the second
while :; do
    case $3 in
      --no-cache) build_args="$build_args --no-cache";;
      --pull) PULL="true";;
      --cmd=*) IFS='=' read -r _ CMD <<< $3;; # split by first '='
      *) break
    esac
    shift
done

echo "Deploy $TYPE docker stack to $USERNAME@$HOST"

read -p "Press [Enter] to continue..."

# If --pull argument is specified,
# pull from docker registry instead of build from source
if [ $PULL = "true" ]; then
  GET_IMAGE="docker pull gcr.io/docker-reghub/pyct"
else
  GET_IMAGE="docker-compose build $build_args"
fi

cd ../

# Zip and upload source code
rm -rf $PROJ_DIR.zip
zip -9 -qr --exclude=*.git* $PROJ_DIR.zip $PROJ_DIR
echo 'Uploading source...'
scp $PROJ_DIR.zip $USERNAME@$HOST:~/

# deploy any python app.py command
if [ $TYPE = 'uni' ]; then
  ssh $USERNAME@$HOST \
    "PROJ_DIR=pyCryptoTrader && \
    rm -rf $PROJ_DIR && \
    unzip -q $PROJ_DIR.zip && \
    cd $PROJ_DIR && \
    \
    export PYCT_CMD=\"$CMD\" && \
    source .env && \
    \
    $GET_IMAGE && \
    \
    docker stack rm pyct && \
    echo \"wait for 10 seconds...\" && \
    sleep 10 && \
    \
    docker stack deploy -c $DOCKER_DIR/docker-stack.yml pyct && \
    echo \"wait for 10 seconds...\" && \
    sleep 10 && \
    \
    docker service logs -f pyct_main"

# deploy parameter optimization
elif [ $TYPE == 'optimize' ]; then
  ssh $USERNAME@$HOST \
    "PROJ_DIR=pyCryptoTrader && \
    rm -rf $PROJ_DIR && \
    unzip -q $PROJ_DIR.zip && \
    cd $PROJ_DIR && \
    source .env && \
    \
    $GET_IMAGE && \
    \
    docker stack rm optimize && \
    echo \"wait for 10 seconds...\" && \
    sleep 10 && \
    \
    docker stack deploy -c $DOCKER_DIR/docker-stack-$TYPE.yml optimize && \
    echo \"wait for 10 seconds...\" && \
    sleep 10 && \
    \
    docker service logs -f optimize_optimize"

else # deploy trader
  ssh $USERNAME@$HOST \
    "PROJ_DIR=pyCryptoTrader && \
    rm -rf $PROJ_DIR && \
    unzip -q $PROJ_DIR.zip && \
    cd $PROJ_DIR && \
    source .env && \
    \
    $GET_IMAGE \
    \
    docker stack rm crypto && \
    docker stack rm data && \
    echo \"wait for 10 seconds...\" && \
    sleep 10 && \
    \
    docker stack deploy -c $DOCKER_DIR/docker-stack-data-stream.yml data && \
    docker stack deploy -c $DOCKER_DIR/docker-stack-$TYPE.yml crypto && \
    echo \"wait for 10 seconds...\" && \
    sleep 10 && \
    \
    docker service logs -f crypto_trade"
fi