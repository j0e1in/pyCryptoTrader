import motor.motor_asyncio as motor
import logging
import pandas as pd
import pymongo

from utils import INF, ms_dt, sec_ms, ex_name, config

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
                                fields_condition={},
                                index_col=None,
                                date_col=None,
                                date_parser=None,
                                df_options={}):
        """ If date_col is provided, date_parser must be as well. """
        fields_condition = {**fields_condition, **{'_id': 0}}


        coll = self.client.get_database(db).get_collection(collection)
        docs = await coll.find(condition, fields_condition).to_list(length=INF)
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

    async def get_ohlcv(self, ex, symbol, start, end, timeframe):
        """ Read ohlcv from mongodb into DataFrame,
            Params
                ex: str or ccxt exchange instance
                symbol: str
                start, end: timestamp
                timeframe: str
        """
        db = config['database']['dbname_exchange']
        condition = self.cond_timestamp_range(start, end)

        ex = ex_name(ex)
        collection = f"{ex}_ohlcv_{self.sym(symbol)}_{timeframe}"

        return await self.read_to_dataframe(db, collection, condition,
                                            index_col='timestamp',
                                            date_col='timestamp',
                                            date_parser=ms_dt)

    async def get_trades(self, ex, symbol, start, end, fields_condition={}):
        db = config['database']['dbname_exchange']
        condition = self.cond_timestamp_range(start, end)
        fields_condition = {**fields_condition, **{'_id': 0}}

        ex = ex_name(ex)
        collection = f"{ex}_trades_{self.sym(symbol)}"

        return await self.read_to_dataframe(db, collection, condition,
                                            fields_condition=fields_condition,
                                            index_col='timestamp',
                                            date_col='timestamp',
                                            date_parser=ms_dt)

    async def insert_ohlcv(self, ohlcv_df, ex, symbol, timeframe, *, coll_prefix=''):
        """ Insert ohlcv dateframe to mongodb. """
        db = config['database']['dbname_exchange']
        ex = ex_name(ex)
        collection = f"{coll_prefix}{ex}_ohlcv_{self.sym(symbol)}_{timeframe}"
        coll = self.client.get_database(db).get_collection(collection)

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

    async def get_ohlcv_of_symbols(self, ex, symbols, start, end):
        """ Returns ohlcvs with all timeframes of symbols in the list. """
        ohlcvs = {}
        timeframes = config['trader']['exchanges'][ex_name(ex)]['timeframes']
        for sym in symbols:
            ohlcvs[sym] = {}
            for tf in timeframes:
                ohlcvs[sym][tf] = await self.get_ohlcv(ex, sym, start, end, tf)
        return ohlcvs

    async def get_trades_of_symbols(self, ex, symbols, start, end, fields_condition=None):
        """ Returns trades of symbols in the list. """
        trades = {}
        timeframes = config['trader']['exchanges'][ex_name(ex)]['timeframes']
        for sym in symbols:
            trades[sym] = await self.get_trades(ex, sym, start, end, fields_condition)
        return trades
