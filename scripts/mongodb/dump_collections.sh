colls=(
  "bitfinex_ohlcv_ETHUSD_12h"
  "bitfinex_ohlcv_ETHUSD_15m"
  "bitfinex_ohlcv_ETHUSD_1d"
  "bitfinex_ohlcv_ETHUSD_1h"
  "bitfinex_ohlcv_ETHUSD_1m"
  "bitfinex_ohlcv_ETHUSD_30m"
  "bitfinex_ohlcv_ETHUSD_3h"
  "bitfinex_ohlcv_ETHUSD_5m"
  "bitfinex_ohlcv_ETHUSD_6h"
)

dest=$HOME/exchange_backup

mkdir -p $dest

for c in ${colls[@]}
do
  mongodump -d exchange -c $c --gzip --archive=$dest/$c.gzip
done