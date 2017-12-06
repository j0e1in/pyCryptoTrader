colls=(
  # "bitfinex_ohlcv_ETHUSD_12h"
  # "bitfinex_ohlcv_ETHUSD_15m"
  # "bitfinex_ohlcv_ETHUSD_1d"
  # "bitfinex_ohlcv_ETHUSD_1h"
  # "bitfinex_ohlcv_ETHUSD_1m"
  # "bitfinex_ohlcv_ETHUSD_30m"
  # "bitfinex_ohlcv_ETHUSD_3h"
  # "bitfinex_ohlcv_ETHUSD_5m"
  # "bitfinex_ohlcv_ETHUSD_6h"
)

src=$HOME/exchange_backup

for c in ${colls[@]}
do
  mongorestore -d exchange2 -c $c --archive=$src/$c.bson
done

# https://docs.mongodb.com/manual/reference/program/mongorestore/#examples