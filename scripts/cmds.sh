# Start trading in backgound
$ nohup python restart.py start_trader.py &

# Stream a log file from remote server
ssh -t j0e1in@35.201.224.121 "tail -f ~/log/start_trader.log"

# Check python programs is running
ps -A | grep python

# Kill all python processes
killall python



## ON LOCAL MACHINE

PROJ_DIR=pyCryptoTrader
USERNAME=j0e1in
IP=crypto.csie.io

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
gcloud docker -- pull gcr.io/docker-reghub/pyct
docker tag gcr.io/docker-reghub/pyct pycryptotrader

# Push built image
docker tag pycryptotrader gcr.io/docker-reghub/pyct
gcloud docker -- push gcr.io/docker-reghub/pyct


## Migrate mongodb
# Backup
docker run -v mongo_data:/volume --rm loomchild/volume-backup backup - > mongo_data.tar.bz2

# Copy to remote
scp mongo_data.tar.bz2 $USERNAME@$IP:~/

# Restore (use scripts/mongodb/mongo_container_setup.sh to restore for first time)
cat mongo_data.tar.bz2 | docker run -i -v mongo_data:/volume --rm loomchild/volume-backup restore -

# Cleanup docker images/containers
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v /etc:/etc:ro spotify/docker-gc

# Start standalone mongo container
docker stop mongo
docker rm mongo
docker run -d \
--name mongo \
--network mongo_net \
--volume mongo_data:/data/db \
mongo:3.6 --auth

# Add traders
python app.py --add-trader="(1492068960851477,bitfinex),(1634221979967223,bitfinex)"


# Authenticate gcloud using key file
gcloud auth activate-service-account --key-file [KEY_FILE]
# Make `docker` command to use `gcloud docker`
gcloud auth configure-docker