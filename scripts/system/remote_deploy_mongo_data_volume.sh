#!/bin/bash

USERNAME=$1
IP=$2

if [ -z $USERNAME ] | [ -z $IP ]; then
  echo "Usage: remote_deploy_mongo_data_volume.sh [USERNAME] [IP]"
  exit 1
fi

echo "Deploy mongo data to $USERNAME@$IP"

read -p "Press [Enter] to continue..."

## Migrate mongodb
# Backup
echo "Backing up mongo_data..."
docker run -v mongo_data:/volume --rm loomchild/volume-backup backup - > ~/mongo_data.tar.bz2

# Copy to remote
echo "Uploading mongo_data..."
scp ~/mongo_data.tar.bz2 $USERNAME@$IP:~/

# Restore (use scripts/mongodb/mongo_container_setup.sh to restore for first time)
echo "Restoring mongo_data..."
ssh $USERNAME@$IP "docker volume create mongo_data && \
                   cat mongo_data.tar.bz2 | docker run -i -v mongo_data:/volume --rm loomchild/volume-backup restore -"
