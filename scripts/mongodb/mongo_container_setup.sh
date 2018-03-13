#!/bin/bash
# !!! Run this file from project root !!!

docker network create mongo_net
docker volume create mongo_data

docker run -d \
--name mongo \
--network mongo_net \
--volume mongo_data:/data/db \
mongo:3.6

MONGO_SERVER_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' mongo)

# Restore data using volume-backup docker image
cat $HOME/mongo_data.tar.bz2 | docker run -i -v mongo_data:/volume --rm loomchild/volume-backup restore -

# Restore data using mongorestore
# unzip ~/ohlcvs.zip
# mongorestore -d exchange --host $MONGO_SERVER_IP ohlcvs
# mongo --host $MONGO_SERVER_IP < scripts/mongodb/create_user.js
# rm -rf ohlcvs

# Restart mongo in auth mode
docker stop mongo
docker rm mongo
docker run -d \
--name mongo \
--network mongo_net \
--volume mongo_data:/data/db \
mongo:3.6 --auth