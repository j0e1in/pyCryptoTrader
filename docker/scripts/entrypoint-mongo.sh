#!/bin/bash

echo ">>>  Starting mongod with config file: settings/mongod.conf-$DEPLOY_ENV.yml  <<<"

mongod --config settings/mongod.conf-$DEPLOY_ENV.yml