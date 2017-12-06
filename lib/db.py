import motor.motor_asyncio as motor
import logging
import pandas as pd
import pymongo

from utils import INF, utcms_dt, sec_ms, exchange_name

pd.options.mode.chained_assignment = None

logger = logging.getLogger()


class EXMongo():

    def __init__(self, *, host='localhost', port=27017, uri=None):
        if uri:
            logger.info(f"Connecting mongo client to {uri}")
            self.client = motor.AsyncIOMotorClient(uri)
        else:
            logger.info(f"Connecting mongo client to {host}:{port}")
            self.client = motor.AsyncIOMotorClient(host, port)

    async def load_exchanges_info(self):
        """
            exchanges: {
                symbols
                timeframes
                start,
                end
            }
        """
        pass

    async def export_to_csv(self, db, collection, path):
        await self._dump_to_file(db, collection, path, 'csv')

    async def _dump_to_file(self, db, collection, path, format):
        df = await self.read_to_dataframe(db, collection)
        if format == 'csv':
            df.to_csv(path, index=False)

    async def read_to_dataframe(self, db, collection, condition={}, *,
                                index_col=None,
                                date_col=None,
                                date_parser=None,
                                df_options={}):
        """ If date_col is provided, date_parser must be as well. """
        coll = self.client.get_database(db).get_collection(collection)
        docs = await coll.find(condition, {'_id': 0}).to_list(length=INF)
        df = pd.DataFrame(data=docs, **df_options)

        if len(df) == 0:
            df = await self.create_empty_df_coll(coll)

        if date_parser and date_col:
            df[date_col] = df[date_col].apply(date_parser)
        elif date_parser and not date_col:
            raise ValueError('date_parser is provided but date_col is not.')
        elif date_col and not date_parser:
            raise ValueError('date_col is provided but date_parser is not.')

        if index_col:
            df.set_index(index_col, inplace=True)

        return df

    async def get_ohlcv(self, exchange, symbol, start, end, timeframe):
        """ Read ohlcv from mongodb into DataFrame,
            Params
                exchange: str or ccxt exchange instance
                symbol: str
                start, end: timestamp
                timeframe: str
        """
        db = 'exchange'
        condition = self.cond_timestamp_range(start, end)

        ex = exchange_name(exchange)
        collection = f"{ex}_ohlcv_{self.sym(symbol)}_{timeframe}"

        return await self.read_to_dataframe(db, collection, condition,
                                            index_col='timestamp',
                                            date_col='timestamp',
                                            date_parser=utcms_dt)

    async def insert_ohlcv(self, ohlcv_df, exchange, symbol, timeframe):
        """ Insert ohlcv dateframe to mongodb. """
        ex = exchange_name(exchange)
        collection = f"test_{ex}_ohlcv_{self.sym(symbol)}_{timeframe}"
        coll = self.client.exchange.get_collection(collection)

        def to_timestamp(ts):
            return sec_ms(ts.timestamp())

        # put 'timestamp' index to first column
        ohlcv_df.reset_index(level=0, inplace=True)
        ohlcv_df.timestamp = ohlcv_df.timestamp.apply(to_timestamp)

        records = ohlcv_df.to_dict(orient='records')

        try:
            await coll.insert_many(records)
        except pymongo.errors.BulkWriteError as error:
            logger.warn(f"Mongodb BulkWriteError: {error}")

    @staticmethod
    async def check_columns(collection, columns):
        sample = await collection.find_one({}, {'_id': 0})
        cols = list(sample.keys())

        if len(cols) != len(columns):
            return False

        for c in columns:
            if c not in cols:
                return False

        return True

    @staticmethod
    def sym(symbol):
        """ Convert BTC/USD -> BTCUSD """
        return ''.join(symbol.split('/'))

    @staticmethod
    def cond_timestamp_range(start, end):
        """ Returns mongo command condition of a timestmap range. """
        return {'timestamp': {'$gte': start, '$lt': end}}

    async def create_empty_df_coll(self, coll):
        """ Fetch fields in the collection and create an empty df with columns. """
        res = await coll.find_one({},{'_id':0})
        return pd.DataFrame(columns=res.keys())




