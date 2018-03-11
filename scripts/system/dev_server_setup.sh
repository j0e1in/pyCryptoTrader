USERNAME=j0e1in

# Create user
adduser --disabled-password --gecos "" $USERNAME
usermod -aG sudo $USERNAME

# Copy ssh pubkey
cp -r .ssh /home/$USERNAME
chown -R $USERNAME:$USERNAME /home/$USERNAME/.ssh

# Install some utilities
sudo apt-get install -y htop zip

#Install Docker
sudo apt-get update
sudo apt-get install \
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

#########################################################################################

## ON LOCAL MACHINE

PROJ_DIR=pyCryptoTrader
OHLCV_DIR=~/mongo_backup
USERNAME=j0e1in
IP=159.89.201.222

scp $OHLCV_DIR/ohlcvs.zip $USERNAME@$IP:~/

# Zip and upload source code
rm -rf $PROJ_DIR.zip
zip -9 -r --exclude=*.git* $PROJ_DIR.zip $PROJ_DIR
scp $PROJ_DIR.zip $USERNAME@$IP:~/
ssh $USERNAME@$IP


## ON REMOTE MACHINE

PROJ_DIR=pyCryptoTrader

rm -rf $PROJ_DIR
unzip $PROJ_DIR.zip
cd $PROJ_DIR

## Manual  operations
# Set password
passwd

# Init GCP SDK
gcloud init

# Pull built image
gcloud docker -- pull gcr.io/docker-reghub/pycryptotrader
docker tag gcr.io/docker-reghub/pycryptotrader pycryptotrader

# or build from source
cd $PROJ_DIR
docker build -t pycryptotrader .


