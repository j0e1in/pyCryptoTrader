#!/bin/bash

mkdir -p Tmp/
cd tmp


# Downlaod ta-lib source
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz

# Install ta-lib
tar xvf ta-lib-0.4.0-src.tar.gz
cd ta-lib
./configure --prefix=/usr
make
sudo make install


# Install python requirements
pip install -r ../requirements.txt