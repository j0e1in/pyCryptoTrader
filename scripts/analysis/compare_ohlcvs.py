from setup import run

from db import EXMongo
from analysis.hist_data import compare_ohlcvs


async def main():
    mongo = EXMongo()
    exchange = 'bitfinex'

    prefix_1 = ''
    prefix_2 = 'tmp_'

    symbols = [
        'BTC/USD',
        'ETH/USD',
        'XRP/USD'
    ]

    tfs = ['3h', '6h', '8h', '10h']

    diff = {}
    for symbol in symbols:
        for tf in tfs:
            diff[f"{symbol}_{tf}"] = await compare_ohlcvs(mongo, exchange, symbol, tf, prefix_1, prefix_2)

    for k, v in diff.items():
        print(f"\n[{k} diff]\n"
              f"open: {len(v[ v.open == False ])}/{len(v.open)}"
              f" | close: {len(v[ v.close == False ])}/{len(v.close)}"
              f" | high: {len(v[ v.high == False ])}/{len(v.high)}"
              f" | low: {len(v[ v.low == False ])}/{len(v.low)}"
              f" | volume: {len(v[ v.volume == False ])}/{len(v.volume)}")


if __name__ == '__main__':
    run(main)