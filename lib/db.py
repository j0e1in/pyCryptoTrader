from datetime import datetime
from pymongo.errors import BulkWriteError
from motor import motor_asyncio
import logging
import pandas as pd
import pymongo

from utils import \
    INF, \
    ms_dt, \
    dt_ms, \
    ex_name, \
    config, \
    rsym, \
    execute_mongo_ops

pd.options.mode.chained_assignment = None


logger = logging.getLogger()

# TODO: Add insert_trades()


class EXMongo():

    def __init__(self, *, host=None, port=None, uri=None, custom_config=None):
        _config = custom_config if custom_config else config
        self.config = _config['database']
        self._config = _config

        if not host:
            host = self.config['default_host']
        if not port:
            port = self.config['default_port']

        if not uri:
            if self.config['auth']:
                user = self.config['username']
                passwd = self.config['password']
                db = self.config['auth_db']
                uri = f"mongodb://{user}:{passwd}@{host}:{port}/{db}"
            else:
                uri = f"mongodb://{host}:{port}/"

        logger.info(f"Connecting mongo client to {host}:{port}")
        self.client = motor_asyncio.AsyncIOMotorClient(uri)

    async def get_exchanges_info(self, ex):
        # TODO: Read exchange summary
        # self.update_exchanges_info()
        # coll_names = await self.client.get_database(self.config['dbname_exchange']).collection_names()
        pass

    async def update_exchanges_info(self):
        # TODO: Update exchange summary
        pass

    async def export_to_csv(self, db, collection, path):
        await self._dump_to_file(db, collection, path, 'csv')

    async def _dump_to_file(self, db, collection, path, format):
        df = await self._read_to_dataframe(db, collection)
        if format == 'csv':
            df.to_csv(path, index=False)

    async def get_ohlcv_start(self, ex, sym, tf):
        """ Get datetime of first ohlcv in a collection. """
        res = await self.get_first_ohclv(ex, sym, tf)
        return ms_dt(res['timestamp'])

    async def get_first_ohclv(self, ex, sym, tf):
        collname = f"{ex}_ohlcv_{rsym(sym)}_{tf}"
        coll = self.get_collection(self.config['dbname_exchange'], collname)
        res = await coll.find({}) \
            .sort([('timestamp', 1)]) \
            .limit(1) \
            .to_list(length=INF)

        if not res:
            raise ValueError(f"{collname} does not exist")

        return res[0]

    async def get_ohlcv_end(self, ex, sym, tf):
        """ Get datetime of last ohlcv in a collection. """
        res = await self.get_last_ohclv(ex, sym, tf)
        return ms_dt(res['timestamp'])

    async def get_last_ohclv(self, ex, sym, tf):
        collname = f"{ex}_ohlcv_{rsym(sym)}_{tf}"
        coll = self.get_collection(self.config['dbname_exchange'], collname)
        res = await coll.find({}) \
            .sort([('timestamp', -1)]) \
            .limit(1) \
            .to_list(length=INF)

        if not res:
            raise ValueError(f"{collname} does not exist")

        return res[0]

    async def get_trades_start(self, ex, sym):
        """ Get datetime of first trades in a collection. """
        collname = f"{ex}_trades_{rsym(sym)}"
        coll = self.get_collection(self.config['dbname_exchange'], collname)
        res = await coll.find({}).sort([('id', 1)]).limit(1).to_list(length=INF)

        if not res:
            raise ValueError(f"{collname} does not exist")

        return ms_dt(res[0]['timestamp'])

    async def get_trades_end(self, ex, sym):
        """ Get datetime of last trades in a collection. """
        collname = f"{ex}_trades_{rsym(sym)}"
        coll = self.get_collection(self.config['dbname_exchange'], collname)
        res = await coll.find({}).sort([('id', -1)]).limit(1).to_list(length=INF)

        if not res:
            raise ValueError(f"{collname} does not exist")

        return ms_dt(res[0]['timestamp'])

    async def get_ohlcv(self, ex, symbol, timeframe, start, end, fields_condition={}, compress=False):
        """ Read ohlcv of 'one' symbol and 'one' timeframe from mongodb into DataFrame,
            Params
                ex: str or ccxt exchange instance
                symbol: str
                start, end: datetime
                timeframe: str
                compress: bool, change data type to smaller ones (eg. float64 -> float32)
                fields_conditions: select/filter some columns (eg. remove 'close' column: {'close': 0})
        """

        db = self.config['dbname_exchange']
        condition = self.cond_timestamp_range(start, end)

        ex = ex_name(ex)
        collection = f"{ex}_ohlcv_{rsym(symbol)}_{timeframe}"

        coll = self.get_collection(db, collection)
        if not await self.coll_exist(coll):
            raise ValueError(f"Collection {collection} does not exist.")

        ohlcv = await self._read_to_dataframe(db, collection, condition,
                                             index_col='timestamp',
                                             date_col='timestamp',
                                             date_parser=ms_dt)
        ohlcv.sort_index(inplace=True)

        if compress:
            # Covert all float colums to minimum float type, which is float32
            selected_ohlcv = ohlcv.select_dtypes(include=['float'])
            selected_ohlcv = selected_ohlcv.apply(pd.to_numeric, downcast='float')
            ohlcv[selected_ohlcv.columns] = selected_ohlcv

        return ohlcv

    async def get_trades(self, ex, symbol, start, end, fields_condition={}, compress=False):
        """ Read ohlcv of 'one' symbol from mongodb into DataFrame. """
        db = self.config['dbname_exchange']
        condition = self.cond_timestamp_range(start, end)
        fields_condition = {**fields_condition, **{'_id': 0}}

        ex = ex_name(ex)
        collection = f"{ex}_trades_{rsym(symbol)}"

        trade = await self._read_to_dataframe(db, collection, condition,
                                             fields_condition=fields_condition,
                                             index_col='timestamp',
                                             date_col='timestamp',
                                             date_parser=ms_dt)
        trade.sort_index(inplace=True)

        if compress:
            # Covert types to significantly reduce memory usage
            trade['price'] = trade['price'].astype('float32', copy=False)
            trade['amount'] = trade['amount'].astype('float32', copy=False)

        trade['id'] = trade['id'].astype('uint', copy=False)
        trade['side'] = trade['side'].astype('category', copy=False)
        trade['symbol'] = trade['symbol'].astype('category', copy=False)

        return trade

    async def get_ohlcvs_of_symbols(self, ex, symbols, timeframes, start, end, fields_condition={}, compress=False):
        """ Returns ohlcvs of multiple timeframes and symbols in an exchange.
            Return
                {
                    'BTC/USD': {
                        '1m': DataFrame(...),
                        '5m': DataFrame(...),
                    },
                }
        """
        ohlcvs = {}
        for sym in symbols:
            ohlcvs[sym] = {}
            for tf in timeframes:
                ohlcvs[sym][tf] = await self.get_ohlcv(ex, sym, tf, start, end, fields_condition, compress)
        return ohlcvs

    async def get_trades_of_symbols(self, ex, symbols, start, end, fields_condition={}, compress=False):
        """ Returns trades of multiple symbols in an exchange.
            Return
                {
                    'BTC/USD': DataFrame(...),
                    'ETH/USD': DataFrame(...),
                }
        """
        trades = {}
        timeframes = self._config['analysis']['exchanges'][ex_name(ex)]['timeframes']
        for sym in symbols:
            trades[sym] = await self.get_trades(ex, sym, start, end, fields_condition, compress)
        return trades

    async def insert_ohlcv(self, ohlcv_df, ex, symbol, timeframe, *, coll_prefix='', upsert=True):
        """ Insert ohlcv dateframe to mongodb. """
        db = self.config['dbname_exchange']
        ex = ex_name(ex)
        coll = f"{coll_prefix}{ex}_ohlcv_{rsym(symbol)}_{timeframe}"
        coll = self.get_collection(db, coll)

        # put 'timestamp' index to first column
        ohlcv_df.reset_index(level=0, inplace=True)
        ohlcv_df.timestamp = ohlcv_df.timestamp.apply(dt_ms)

        records = ohlcv_df.to_dict(orient='records')

        ops = []
        for rec in records:
            ops.append(
                pymongo.UpdateOne(
                    {'timestamp': rec['timestamp']},
                    {'$set': rec},
                    upsert=True))

            if len(ops) > 10000:
                await execute_mongo_ops(coll.bulk_write(ops))
                ops = []

        await execute_mongo_ops(coll.bulk_write(ops))

    async def _read_to_dataframe(self, db, collection, condition={}, *,
                                fields_condition={},
                                index_col=None,
                                date_col=None,
                                date_parser=None,
                                df_options={}):
        """ If date_col is provided, date_parser must be as well. """
        fields_condition = {**fields_condition, **{'_id': 0}}

        coll = self.get_collection(db, collection)

        # Process result at once
        docs = await coll.find(condition, fields_condition).to_list(length=INF)
        df = pd.DataFrame(data=docs, **df_options)

        # Use limited length to process result block by block
        # Since uncompressed df will endup using same amount of memory as processing result at once,
        # there's no reason to use this method.
        #
        # cursor = coll.find(condition, fields_condition)
        # LEN_MAX = 1000
        # doc = await cursor.to_list(length=LEN_MAX)
        # df = pd.DataFrame(data=doc, **df_options)

        # doc = await cursor.to_list(length=LEN_MAX)
        # while len(doc) > 0:
        #     tmp = pd.DataFrame(data=doc, index=np.arange(len(doc)).tolist(), columns=df.columns, **df_options)
        #     df = pd.concat([df, tmp], ignore_index=True)
        #     doc = await cursor.to_list(length=LEN_MAX)

        if len(df) == 0:
            df = await self.create_empty_df_of_coll(coll)

        if date_parser and date_col:
            df[date_col] = df[date_col].apply(date_parser)
        elif date_parser and not date_col:
            raise ValueError('date_parser is provided but date_col is not.')
        elif date_col and not date_parser:
            raise ValueError('date_col is provided but date_parser is not.')
        if index_col:
            df.set_index(index_col, inplace=True)

        return df

    def get_database(self, dbname):
        return getattr(self.client, dbname)

    def get_collection(self, dbname, collname):
        db = getattr(self.client, dbname)
        coll = getattr(db, collname)
        return coll

    async def get_my_trades(self, ex, start, end):
        db = self.config['dbname_trade']
        coll = f"{ex}_trades"
        coll = self.get_collection(db, coll)
        trades = await coll.find(self.cond_timestamp_range(start, end), {'_id': 0}) \
                                 .sort([('timestamp', 1)]) \
                                 .to_list(length=INF)
        return trades

    async def get_my_last_trade(self, ex, symbol):
        db = self.config['dbname_trade']
        coll = f"{ex}_trades"
        coll = self.get_collection(db, coll)
        trade = await coll.find({'symbol': symbol}, {'_id': 0}) \
                          .sort([('timestamp', -1)]) \
                          .limit(1) \
                          .to_list(length=INF)
        return trade[0] if trade else {}

    async def get_last_order_group_id(self, ex):
        db = self.config['dbname_trade']
        coll = f"{ex}_created_orders"
        coll = self.get_collection(db, coll)
        order = await coll.find({}, {'_id': 0}) \
                          .sort([('group_id', -1)]) \
                          .limit(1) \
                          .to_list(length=INF)
        return order[0]['group_id'] if order else 0

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
    def cond_timestamp_range(start, end):
        """ Returns mongo command condition of a timestmap range. """
        return {'timestamp': {'$gte': dt_ms(start), '$lt': dt_ms(end)}}

    @staticmethod
    async def coll_exist(coll):
        if not isinstance(coll, motor_asyncio.AsyncIOMotorCollection):
            raise ValueError("Requries an instance of AsyncIOMotorCollection")

        return False if not await coll.find_one() else True

    async def create_empty_df_of_coll(self, coll):
        """ Fetch fields in the collection and create an empty df with columns. """
        res = await coll.find_one({}, {'_id': 0})
        return pd.DataFrame(columns=res.keys())
