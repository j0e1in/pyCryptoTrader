#!/bin/bash

PROJ_DIR=pyCryptoTrader
CUR_DIR=$(pwd)

# Check if current path ends with project name
if [[ "$CUR_DIR" != */$PROJ_DIR ]]; then
  echo "ERROR: Please run this script at project root."
  exit 1
fi

REMOTE=$1
TYPE=$2

# Split remote by '@'
IFS='@' read -r -a REMOTE <<< $REMOTE

USERNAME=${REMOTE[0]}
HOST=${REMOTE[1]}

if [ -z $USERNAME ] | [ -z $HOST ] | [ -z $TYPE ]; then
  echo "Usage: remote_deploy_docker_stack.sh [username]@[host] [type] [--no-cache]"
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

echo "Deploy $TYPE docker stack to $USERNAME@$HOST"

read -p "Press [Enter] to continue..."

cd ../

# Zip and upload source code
rm -rf $PROJ_DIR.zip
zip -9 -qr --exclude=*.git* $PROJ_DIR.zip $PROJ_DIR
echo 'Uploading source...'
scp $PROJ_DIR.zip $USERNAME@$HOST:~/
ssh $USERNAME@$HOST "PROJ_DIR=pyCryptoTrader && \
                   rm -rf $PROJ_DIR && \
                   unzip -q $PROJ_DIR.zip && \
                   cd $PROJ_DIR && \
                   \
                   docker-compose build $build_args && \
                   \
                   docker stack rm crypto && \
                   docker stack rm data_stream && \
                   echo \"wait for 20 seconds...\" && \
                   sleep 20 && \
                   \
                   docker stack deploy -c docker-stack-data-stream.yml data_stream && \
                   docker stack deploy -c docker-stack-$TYPE.yml crypto && \
                   echo \"wait for 10 seconds...\" && \
                   sleep 10 && \
                   \
                   docker service logs -f crypto_trade"


