#!/bin/bash

unzip ~/ohlcvs.zip

docker network create mongo_net
docker volume create mongo_data

docker run -d \
--name mongo \
--network mongo_net \
--volume mongo_data:/data/db \
mongo:3.6

MONGO_SERVER_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' mongo)

mongorestore -d exchange --host $MONGO_SERVER_IP ohlcvs

mongo --host $MONGO_SERVER_IP < scripts/mongodb/create_user.js

rm -rf ohlcvs
