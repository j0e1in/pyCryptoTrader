#!/bin/bash

USERNAME=$1
IP=$2

if [ -z $USERNAME ] | [ -z $IP ]; then
  echo "Usage: remote_deploy_mongo_data_volume.sh [USERNAME] [IP]"
fi


## Migrate mongodb
# Backup
docker run -v mongo_data:/volume --rm loomchild/volume-backup backup - > mongo_data.tar.bz2

# Copy to remote
scp mongo_data.tar.bz2 $USERNAME@$IP:~/

# Restore (use scripts/mongodb/mongo_container_setup.sh to restore for first time)
ssh $USERNAME@$IP "docker volume create mongo_data && \
                   cat mongo_data.tar.bz2 | docker run -i -v mongo_data:/volume --rm loomchild/volume-backup restore -"
