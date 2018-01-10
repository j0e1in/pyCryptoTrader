from setup import setup, run
setup()

from db import EXMongo


async def main():
    mongo = EXMongo(host='localhost', port=27017)

    collections = [
        'bitfinex_ohlcv_BTCUSD_12h',
        'bitfinex_ohlcv_BTCUSD_15m',
        'bitfinex_ohlcv_BTCUSD_1d',
        'bitfinex_ohlcv_BTCUSD_1h',
        'bitfinex_ohlcv_BTCUSD_1m',
        'bitfinex_ohlcv_BTCUSD_30m',
        'bitfinex_ohlcv_BTCUSD_3h',
        'bitfinex_ohlcv_BTCUSD_5m',
        'bitfinex_ohlcv_BTCUSD_6h',
        'bitfinex_ohlcv_ETHUSD_12h',
        'bitfinex_ohlcv_ETHUSD_15m',
        'bitfinex_ohlcv_ETHUSD_1d',
        'bitfinex_ohlcv_ETHUSD_1h',
        'bitfinex_ohlcv_ETHUSD_1m',
        'bitfinex_ohlcv_ETHUSD_30m',
        'bitfinex_ohlcv_ETHUSD_3h',
        'bitfinex_ohlcv_ETHUSD_5m',
        'bitfinex_ohlcv_ETHUSD_6h'
    ]

    for coll in collections:
        path = '../data/' + coll + '.csv'
        print("Exporting", coll)
        await mongo.export_to_csv('exchange', coll, path)



if __name__ == '__main__':
    run(main)