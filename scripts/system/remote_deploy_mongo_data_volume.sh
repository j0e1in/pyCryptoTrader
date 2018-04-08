#!/bin/bash

REMOTE=$1

# Split remote by '@'
IFS='@' read -r -a REMOTE <<< $REMOTE

USERNAME=${REMOTE[0]}
HOST=${REMOTE[1]}

if [ -z $USERNAME ] | [ -z $HOST ]; then
  echo "Usage: remote_deploy_mongo_data_volume.sh [username]@[host]"
  exit 1
fi

echo "Deploy mongo data to $USERNAME@$HOST"

read -p "Press [Enter] to continue..."

## Migrate mongodb
# Backup
echo "Backing up mongo_data..."
docker run -v mongo_data:/volume --rm loomchild/volume-backup backup - > ~/mongo_data.tar.bz2

# Copy to remote
echo "Uploading mongo_data..."
scp ~/mongo_data.tar.bz2 $USERNAME@$HOST:~/

# Restore (use scripts/mongodb/mongo_container_setup.sh to restore for first time)
echo "Restoring mongo_data..."
ssh $USERNAME@$HOST "docker volume create mongo_data && \
                     cat mongo_data.tar.bz2 | docker run -i -v mongo_data:/volume --rm loomchild/volume-backup restore -"
