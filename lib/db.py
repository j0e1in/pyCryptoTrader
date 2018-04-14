from collections import MutableMapping
from motor import motor_asyncio
from redis import StrictRedis

import asyncio
import logging
import pandas as pd
import pymongo
import pickle
import six
import re

from utils import \
    INF, \
    MIN_DT, \
    ms_dt, \
    dt_ms, \
    ex_name, \
    config, \
    rsym, \
    load_keys, \
    execute_mongo_ops

pd.options.mode.chained_assignment = None

logger = logging.getLogger('pyct')


class EXMongo():

    def __init__(self, *,
                 host=None,
                 port=None,
                 uri=None,
                 ssl=False,
                 cert_file=None,
                 ca_file=None,
                 custom_config=None):
        self._config = custom_config or config
        self.config = self._config['database']

        host = host or self.config['default_host']
        port = port or self.config['default_port']

        if ssl:
            cert_file = cert_file or self.config['cert']
            ca_file = ca_file or self.config['ca']
        else:
            cert_file = None
            ca_file = None

        if not uri:
            if self.config['auth']:
                user = self.config['username']
                passwd = load_keys()['mongo_passwd']
                db = self.config['auth_db']
                uri = f"mongodb://{user}:{passwd}@{host}:{port}/{db}"
            else:
                uri = f"mongodb://{host}:{port}/"

        self.host = host
        self.port = port

        logger.info(f"Connecting mongo client to {host}:{port}")
        self.client = motor_asyncio.AsyncIOMotorClient(
            uri, ssl_certfile=cert_file, ssl_ca_certs=ca_file)

    async def export_to_csv(self, db, collection, path):
        await self._dump_to_file(db, collection, path, 'csv')

    async def _dump_to_file(self, db, collection, path, format):
        df = await self._read_to_dataframe(db, collection)
        if format == 'csv':
            df.to_csv(path, index=False)

    async def get_ohlcv_start(self, ex, sym, tf, exception=True):
        """ Get datetime of first ohlcv in a collection. """
        res = await self.get_first_ohclv(ex, sym, tf, exception)
        return ms_dt(res['timestamp'])

    async def get_first_ohclv(self, ex, sym, tf, exception=True):
        collname = f"{ex}_ohlcv_{rsym(sym)}_{tf}"
        coll = self.get_collection(self.config['dbname_exchange'], collname)
        res = await coll.find({}) \
            .sort([('timestamp', 1)]) \
            .limit(1) \
            .to_list(length=INF)

        if not res:
            if exception:
                raise ValueError(f"{collname} does not exist")
            else:
                # if asked not to raise exception, return MIN_DT instead
                return MIN_DT

        return res[0]

    async def get_ohlcv_end(self, ex, sym, tf, exception=True):
        """ Get datetime of last ohlcv in a collection. """
        res = await self.get_last_ohclv(ex, sym, tf, exception)
        return ms_dt(res['timestamp'])

    async def get_last_ohclv(self, ex, sym, tf, exception=True):
        collname = f"{ex}_ohlcv_{rsym(sym)}_{tf}"
        coll = self.get_collection(self.config['dbname_exchange'], collname)
        res = await coll.find({}) \
            .sort([('timestamp', -1)]) \
            .limit(1) \
            .to_list(length=INF)

        if not res:
            if exception:
                raise ValueError(f"{collname} does not exist")
            else:
                # if asked not to raise exception, return MIN_DT instead
                return MIN_DT

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

    async def get_ohlcv(self, ex, symbol, timeframe, start, end,
                        fields_condition={}, compress=False, coll_prefix=''):
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
        collection = f"{coll_prefix}{ex}_ohlcv_{rsym(symbol)}_{timeframe}"

        coll = self.get_collection(db, collection)
        if not await self.coll_exist(coll):
            raise ValueError(f"Collection {collection} does not exist.")

        ohlcv = await self._read_to_dataframe(db, collection, condition,
                                             fields_condition=fields_condition,
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
                    upsert=upsert))

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


class DataStoreFactory():

    def __init__(self, custom_config=None):
        self._config = custom_config or config
        self.config = self._config['datastore']

        self.redis = StrictRedis(host=self.config['default_host'],
                                 port=self.config['default_port'],
                                 password=load_keys()['redis_passwd'])

    def update_redis(self, host=None, port=None, password=''):
        args = self.redis.connection_pool.connection_kwargs
        host = host if host else args['host']
        port = port if port else args['port']
        password = password if password else args['password']

        self.redis = StrictRedis(host=host,
                                 port=port,
                                 password=password)

    def create(self, name):
        """ Create a named container """
        return DataStoreContainer(name)


class DataStoreContainer(MutableMapping):
    serializer = pickle

    def __init__(self, name):
        self._setattr('name', name)
        self._setattr('serializer', self.serializer)

    def _getattr(self, key):
        return super(DataStoreContainer).__getattr__(key)

    def _setattr(self, key, val):
        super().__setattr__(key, val)

    def _delattr(self, key):
        super().__delattr__(key)

    def hasattr(self, key):
        if key in self.__dict__:
            return self._getattr(key)

        val = Datastore.redis.hget(self.name, key)
        return True if val else False

    def __getattr__(self, key):
        if key in self.__dict__:
            return self._getattr(key)

        val = Datastore.redis.hget(self.name, key)

        if not val:
            raise AttributeError(f"{repr(self)} has no attribute `{key}`")

        try:
            res = self.serializer.loads(val)
        except pickle.UnpicklingError as err:
            logger.error(f"{err.__class__} {err}")
            return None
        else:
            return res

    def __setattr__(self, key, val):
        if self._valid_name(key):
            val = self.serializer.dumps(val)
            Datastore.redis.hset(self.name, key, val)
        else:
            raise ValueError(f"`{key}` is not a valid attribute name")

    def __getitem__(self, key):
        return self.__getattr__(key)

    def __setitem__(self, key, val):
        self.__setattr__(key, val)

    def __delitem__(self, key):
        if Datastore.redis.hexists(self.name, key):
            Datastore.redis.hdel(self.name, key)
        else:
            raise AttributeError(f"{repr(self)} has no attribute `{key}`")

    def __getstate__(self):
        """ Called when this object is being serialized """
        return (self.name)

    def __setstate__(self, state):
        """ Called when this object is being deserialized """
        (name) = state

        self._setattr('name', name)
        self._setattr('serializer', self.serializer)

    def __repr__(self):
        """ Return a string representation of the object """
        return f"DataStoreContainer({self.name}, " \
               f"{self.keys()})"

    def __eq__(self, obj):
        if hasattr(obj, 'name') and obj.name == self.name \
        and hasattr(obj, 'serializer') and obj.serializer == self.serializer:
            return True
        else:
            return False

    def __dir__(self):
        return [*['name', 'serializer'], *self.keys()]

    def __iter__(self):
        keys = self.keys()
        for k in keys:
            yield k, getattr(self, k)

    def __len__(self):
        return len(Datastore.redis.hkeys(self.name))

    def items(self):
        return self.__iter__()

    def keys(self):
        _keys = []
        for k in Datastore.redis.hkeys(self.name):
            _keys.append(str(k, 'UTF-8'))
        return _keys

    def get(self, attr, default_val):
        """ Get the attribute, if the attribute wasn't set, return default_val """
        try:
            attr in self
        except AttributeError:
            return default_val
        else:
            return self[attr]

    def sync(self, ds_list, obj):
        """ Store every attribute (of obj) in ds_list to datastore. """
        for attr in ds_list:
            self[attr] = getattr(obj, attr)

    async def sync_routine(self, ds_list, obj):
        while True:
            await asyncio.sleep(2)
            self.sync(ds_list, obj)

    def clear(self):
        Datastore.redis.delete(self.name)

    @classmethod
    def _valid_name(cls, key):
        """
        Check whether a key is a valid attribute name.
        A key may be used as an attribute if:
         * It is a string
         * It matches /^[A-Za-z][A-Za-z0-9_]*$/ (i.e., a public attribute)
         * The key doesn't overlap with any class attributes (for Attr,
            those would be 'get', 'items', 'keys', 'values', 'mro', and
            'register').
        """
        return (isinstance(key, six.string_types)
                and re.match('^[A-Za-z_][A-Za-z0-9_]*$', key)
                and not hasattr(cls, key))


Datastore = DataStoreFactory()
