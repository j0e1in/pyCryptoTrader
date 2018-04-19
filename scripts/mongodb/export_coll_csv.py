from setup import run, root_dir

from db import EXMongo
from utils import config, rsym

async def main():
    mongo = EXMongo()

    symbols = [
        'BTC/USD',
        'ETH/USD'
    ]
    tfs = [
        # '1m',
        '1h'
    ]

    for sym in symbols:
        for tf in tfs:
            collname = f"bitfinex_ohlcv_{rsym(sym)}_{tf}"

            await mongo.export_to_csv(
                config['database']['dbname_exchange'],
                collname,
                f"{root_dir}/data/{collname}")


if __name__ == '__main__':
    run(main)