#!/bin/bash

USERNAME=j0e1in
HOST=crypto.csie.io
SRC=$USERNAME@$HOST:~
DEST=~

ssh $USERNAME@$HOST \
  "docker swarm init && \
  \
  docker volume create mongo_data && \
  docker volume create redis_data && \
  \
  docker network create mongo_net_swarm -d overlay && \
  docker network create redis_net_swarm -d overlay && \
  \
  docker network create mongo_net && \
  docker network create redis_net"

echo "ssh $USERNAME@$HOST \"docker run -v mongo_data:/volume --rm loomchild/volume-backup backup - > mongo_data.tar.bz2\""
ssh $USERNAME@$HOST "docker run -v mongo_data:/volume --rm loomchild/volume-backup backup - > mongo_data.tar.bz2"

# Copy db from remote
echo "scp $SRC/mongo_data.tar.bz2 $DEST/"
scp $SRC/mongo_data.tar.bz2 $DEST/

# Restore (use scripts/mongodb/mongo_container_setup.sh to restore for first time)
echo "cat $DEST/mongo_data.tar.bz2 | docker run -i -v mongo_data:/volume --rm loomchild/volume-backup restore -"
cat $DEST/mongo_data.tar.bz2 | docker run -i -v mongo_data:/volume --rm loomchild/volume-backup restore -
