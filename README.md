# pyCryptoTrader

A full-package program for trading cryptocurrencies automatically, including data fetching, back-testing, and automatic trading.

**NOTE**: This project requires some modification to work properly, for example, changing docker repository. It's not ready for public use yet. <br><br>
**THIS IS FOR DEMONSTRATION PURPOSE ONLY.**

# Requirements

- Ubuntu 16.04 (Recommended)
- Mongo 3.6+
- Docker 17.12+ (Optional, recommended)
- Docker Compose 1.19.0+ (Optional, required if using docker)
- GCP SDK (gcloud) (Optional)

**Note**: A Ubuntu 16.04 server setup script is available, just execute

`$ ssh [user]@[ip] < ./scripts/system/dev_server_setup.sh`

and above tools will be installed.

# Setup

## With Docker

```sh
# Setup mongo container: restore mongodb, create network and volume, and then start the container in auth mode.
./scripts/mongodb/setup_mongo_container.sh mongo_data.tar.bz2

## Pull docker image or build from source
# Pull image from gcr
gcloud init # Only required at the first time
gcloud docker -- pull gcr.io/docker-reghub/pyct

# Build from source
docker-compose build

# Enable docker swarm mode
docker swarm init

# Start trading (can modify arguments in `services > trade > command` in docker-compose.yml to meet specific needs)
docker stack deploy -c docker-compose.yml crypto
```

**Note:** If docker volume mongo_data is setup, can execute

`$./scripts/system/remote_deploy_docker_stack.sh` on local project root or

`$./scripts/system/local_deploy_docker_stack.sh` on remote project root

to quickly build and deploy.

## Without Docker

```sh

```

# Usage

## With Docker

```sh
# Run with docker-compose
docker-compose -f [docker-compose.yml] up

# Run with docker stack
# (only useful for starting trader, becuase other programs are not services)
docker stack deploy -c [docker-compose.yml] [stack-name]
```

**Note:** Make sure no running container is using mongo_data volume before startup other mongo containers.

### Examples

```sh
# Fetch ohlcvs
docker-compose -f docker/fetch_ohlcvs/docker-compose.yml up

# Start trader
docker stack deploy -c docker-compose-production.yml crypto
```

**Note:** Customized arguments can be edited in corresponding docker-compose.yml, all arguments are the same as below.

## Without Docker

- Use one of the options below to run a task.
- Use only one option at a time.


- Add `-h` or `--help` after a task argument to print available arguments for the task.

```sh
python app.py --help
optional arguments:
  -h, --help            show this help message and exit
  --build-ohlcvs        Execute build_ohlcv.py
  --fetch-ohlcvs        Execute fetch_all_ohlcvs.py
  --fetch-trades        Execute fetch_all_trades.py
  --optimize            Execute optimize_params.py
  --backtest            Execute backtest.py
  --setup-mongo-container
                        Execute setup_mongo_container.sh
  --create-mongo-index  Execute create_index.js
  --create-mongo-user   Execute create_user.js
  --drop-ohlcvs         Execute drop_ohlcvs.js
  --drop-trades         Execute drop_ohlcvs.js
  --start-trader        Execute start_trader.py
  --restart-trader      Execute restart_trader.py
```

## Examples

```sh
# Build ohlcvs start from their most recent datetime
python app.py --build-ohlcvs

# Build ohlcvs start from first record of 1m ohlcv
python app.py --build-ohlcvs --from-start

# Fetch ohlcvs start from their most recent records to current time
python app.py --fetch-ohlcvs

# Fetch ohlcvs and do not replace existing ohlcvs
python app.py --fetch-ohlcvs --no-upsert
```

# Useful Commands

```sh
# Pull image from gcr
gcloud docker -- pull gcr.io/docker-reghub/pyct
# Or use docker-compose to pull
docker-compose push

# Push image to gcr
gcloud docker -- push gcr.io/docker-reghub/pyct
# Or use docker-compose to push
docker-compose pull

# Note: docker-compose push/pull require gcloud push/pull at the first time to gain access permission

```

