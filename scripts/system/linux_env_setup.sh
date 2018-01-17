#!/bin/bash

export NEW_MONGO_DATA_LOC=/new/location/mongodb/

mkdir -p Tmp/
cd Tmp


# Downlaod ta-lib source
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz

# Install ta-lib
tar xvf ta-lib-0.4.0-src.tar.gz
cd ta-lib
./configure --prefix=/usr
make
sudo make install


# Install python requirements
pip install -r ../../../requirements.txt


# Install mpl_finance
git clone https://github.com/matplotlib/mpl_finance.git
cd mpl_finance
python setup.py install


# Install Mongodb
sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv 2930ADAE8CAF5059EE73BB4B58712A2291FA4AD5
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu xenial/mongodb-org/3.6 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-3.6.list

sudo apt-get update
sudo apt-get install -y mongodb-org
sudo service mongod start

# Link default mongo data path to a new location
# sudo service mongod stop
# sudo mv /var/lib/mongodb $NEW_MONGO_DATA_LOC
# sudo ln -s /new/disk/mongodb/ /var/lib/mongodb
# sudo chown mongodb:mongodb $NEW_MONGO_DATA_LOC
# sudo service mongod start