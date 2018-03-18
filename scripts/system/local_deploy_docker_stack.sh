#!/bin/bash

PROJ_DIR=pyCryptoTrader
CUR_DIR=$(pwd)

if [[ "$CUR_DIR" != */$PROJ_DIR ]]; then
  echo "ERROR: Please run this script at project root."
  exit 1
fi

docker-compose build
docker stack rm crypto
echo "wait for 20 seconds..."
sleep 20

docker stack deploy -c docker-compose-production.yml crypto
echo "wait for 10 seconds..."
sleep 10

docker service logs -f crypto_trade"