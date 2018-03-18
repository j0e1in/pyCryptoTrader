#!/bin/bash

TYPE=$1

PROJ_DIR=pyCryptoTrader
CUR_DIR=$(pwd)

USERNAME=j0e1in
IP=crypto.csie.io

if [[ "$CUR_DIR" != */$PROJ_DIR ]]; then
  echo "ERROR: Please run this script at project root."
  exit 1
fi

if [ -z $TYPE ]; then
  TYPE=test
fi

echo "Deploying docker stack to $USERNAME@$IP..."

cd ../

# Zip and upload source code
rm -rf $PROJ_DIR.zip
zip -9 -qr --exclude=*.git* $PROJ_DIR.zip $PROJ_DIR
scp $PROJ_DIR.zip $USERNAME@$IP:~/
ssh $USERNAME@$IP "PROJ_DIR=pyCryptoTrader && \
                   rm -rf $PROJ_DIR && \
                   unzip -q $PROJ_DIR.zip && \
                   cd $PROJ_DIR && \
                   docker-compose build && \
                   docker stack rm crypto && \
                   echo \"wait for 20 seconds...\" && \
                   sleep 20 && \
                   docker stack deploy -c docker-compose-$TYPE.yml crypto && \
                   echo \"wait for 10 seconds...\" && \
                   sleep 10 && \
                   docker service logs -f crypto_trade"


