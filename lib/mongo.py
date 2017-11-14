import motor.motor_asyncio as motor
import logging
import pandas as pd

from utils import ld_to_dl, INF

logger = logging.getLogger()


class Mongo():

    def __init__(self, *, host='localhost', port=27017, uri=None):
        if uri:
            logger.info(f"Connecting mongo client to {uri}")
            self.client = motor.AsyncIOMotorClient(uri)
        else:
            logger.info(f"Connecting mongo client to {host}:{port}")
            self.client = motor.AsyncIOMotorClient(host, port)

    async def export_to_csv(self, db, collection, path):
        await self._dump_to_file(db, collection, path, 'csv')

    async def _dump_to_file(self, db, collection, path, format):
        df = await self.read_to_dataframe(db, collection)
        if format == 'csv':
            df.to_csv(path, index=False)

    async def read_to_dataframe(self, db, collection, condition={}, *,
                                date_parser=None,
                                date_col=None,
                                index_col=None,
                                df_options={}):
        coll = self.client.get_database(db).get_collection(collection)
        docs = await coll.find(condition, {'_id': 0}).to_list(length=INF)
        df = pd.DataFrame(data=docs, **df_options)

        if date_parser and date_col:
            df[date_col] = df[date_col].apply(date_parser)
        elif date_parser and not date_col:
            raise ValueError('date_parser is provided but date_col is not.')
        elif date_col and not date_parser:
            raise ValueError('date_col is provided but date_parser is not.')

        if index_col:
            df = df.set_index(index_col)

        return df

    @staticmethod
    async def check_colums(collection, colums):
        sample = await collection.find_one()
        cols = list(colums.keys())

        if len(cols) != len(colums):
            return False

        for c in colums:
            if c not in cols:
                return False

        return True
