#!/bin/bash

USERNAME=j0e1in
IP=0.0.0.0 # change this

# Execute over ssh
# ssh $USERNAME@$IP "bash -s" < scripts/system/dev_server_setup.sh

# Create user
adduser --disabled-password --gecos "" $USERNAME
usermod -aG sudo $USERNAME

# Copy ssh pubkey
cp -r .ssh /home/$USERNAME
chown -R $USERNAME:$USERNAME /home/$USERNAME/.ssh

sudo apt-get update

# Install some utilities
sudo apt-get install -y htop zip

#Install Docker
sudo apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    software-properties-common

curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
sudo add-apt-repository \
   "deb [arch=amd64] https://download.docker.com/linux/ubuntu \
   $(lsb_release -cs) \
   stable"

sudo apt-get update
sudo apt-get install -y docker-ce docker-compose

# Giving non-root access ( reboot to take effect)
sudo usermod -aG docker $USERNAME

# Install gcloud
export CLOUD_SDK_REPO="cloud-sdk-$(lsb_release -c -s)"
echo "deb http://packages.cloud.google.com/apt $CLOUD_SDK_REPO main" | sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -
sudo apt-get update && sudo apt-get install -y google-cloud-sdk

# Install mongo client
sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv 2930ADAE8CAF5059EE73BB4B58712A2291FA4AD5
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu xenial/mongodb-org/3.6 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-3.6.list
sudo apt-get update
sudo apt-get install -y mongodb-org

sudo reboot
