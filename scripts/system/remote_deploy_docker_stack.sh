#!/bin/bash

PROJ_DIR=pyCryptoTrader
CUR_DIR=$(pwd)

USERNAME=$1
IP=$2
TYPE=$3

if [[ "$CUR_DIR" != */$PROJ_DIR ]]; then
  echo "ERROR: Please run this script at project root."
  exit 1
fi

if [ -z $USERNAME ] | [ -z $IP ] | [ -z $TYPE ]; then
  echo "Usage: remote_deploy_mongo_data_volume.sh [USERNAME] [IP] [TYPE]"
  exit 1
fi

echo "Deploy $TYPE docker stack to $USERNAME@$IP"

read -p "Press [Enter] to continue..."

cd ../

# Zip and upload source code
rm -rf $PROJ_DIR.zip
zip -9 -qr --exclude=*.git* $PROJ_DIR.zip $PROJ_DIR
scp $PROJ_DIR.zip $USERNAME@$IP:~/
ssh $USERNAME@$IP "PROJ_DIR=pyCryptoTrader && \
                   rm -rf $PROJ_DIR && \
                   unzip -q $PROJ_DIR.zip && \
                   cd $PROJ_DIR && \
                   \
                   docker-compose build && \
                   \
                   docker stack rm crypto && \
                   echo \"wait for 20 seconds...\" && \
                   sleep 20 && \
                   \
                   docker stack deploy -c docker-compose-$TYPE.yml crypto && \
                   echo \"wait for 10 seconds...\" && \
                   sleep 10 && \
                   \
                   docker service logs -f crypto_trade"


