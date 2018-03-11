#!/bin/bash

docker run -d \
--network mongo_net \
--volume "$(pwd)":/app \
pycryptotrader \
python app.py --optimize --args "optimize --prefix stochrsi -s 210001 -e 220000"

docker run -d \
--network mongo_net \
--volume "$(pwd)":/app \
pycryptotrader \
python app.py --optimize --args "optimize --prefix stochrsi -s 220001 -e 230000"

docker run -d \
--network mongo_net \
--volume "$(pwd)":/app \
pycryptotrader \
python app.py --optimize --args "optimize --prefix stochrsi -s 230001 -e 240000"

docker run -d \
--network mongo_net \
--volume "$(pwd)":/app \
pycryptotrader \
python app.py --optimize --args "optimize --prefix stochrsi -s 240001 -e 250000"

docker run -d \
--network mongo_net \
--volume "$(pwd)":/app \
pycryptotrader \
python app.py --optimize --args "optimize --prefix stochrsi -s 250001 -e 260000"

docker run -d \
--network mongo_net \
--volume "$(pwd)":/app \
pycryptotrader \
python app.py --optimize --args "optimize --prefix stochrsi -s 260001 -e 270000"


# docker run -d \
# --network mongo_net \
# --volume "$(pwd)"/private:/app/private \
# --volume "$(pwd)"/settings:/app/settings \
# --volume "$(pwd)"/data:/app/data \
# pycryptotrader \


# python app.py --optimize --args "optimize --prefix stochrsi -s 1 -e 10000"
# python app.py --optimize --args "optimize --prefix stochrsi -s 10001 -e 20000"
# python app.py --optimize --args "optimize --prefix stochrsi -s 20001 -e 30000"
# python app.py --optimize --args "optimize --prefix stochrsi -s 30001 -e 40000"
# python app.py --optimize --args "optimize --prefix stochrsi -s 40001 -e 50000"
# python app.py --optimize --args "optimize --prefix stochrsi -s 50001 -e 60000"
# python app.py --optimize --args "optimize --prefix stochrsi -s 60001 -e 70000"

# python app.py --optimize --args "optimize --prefix stochrsi -s 70001 -e 80000"
# python app.py --optimize --args "optimize --prefix stochrsi -s 80001 -e 90000"
# python app.py --optimize --args "optimize --prefix stochrsi -s 90001 -e 100000"
# python app.py --optimize --args "optimize --prefix stochrsi -s 100001 -e 110000"
# python app.py --optimize --args "optimize --prefix stochrsi -s 110001 -e 120000"
# python app.py --optimize --args "optimize --prefix stochrsi -s 120001 -e 130000"
# python app.py --optimize --args "optimize --prefix stochrsi -s 130001 -e 140000"

# python app.py --optimize --args "optimize --prefix stochrsi -s 140001 -e 150000"
# python app.py --optimize --args "optimize --prefix stochrsi -s 150001 -e 160000"
# python app.py --optimize --args "optimize --prefix stochrsi -s 160001 -e 170000"
# python app.py --optimize --args "optimize --prefix stochrsi -s 170001 -e 180000"
# python app.py --optimize --args "optimize --prefix stochrsi -s 180001 -e 190000"
# python app.py --optimize --args "optimize --prefix stochrsi -s 190001 -e 200000"
# python app.py --optimize --args "optimize --prefix stochrsi -s 200001 -e 210000"

# python app.py --optimize --args "optimize --prefix stochrsi -s 210001 -e 220000"
# python app.py --optimize --args "optimize --prefix stochrsi -s 220001 -e 230000"
# python app.py --optimize --args "optimize --prefix stochrsi -s 230001 -e 240000"
# python app.py --optimize --args "optimize --prefix stochrsi -s 240001 -e 250000"
# python app.py --optimize --args "optimize --prefix stochrsi -s 250001 -e 260000"
# python app.py --optimize --args "optimize --prefix stochrsi -s 260001 -e 270000"

