import motor.motor_asyncio as motor
import logging
import pandas

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

    async def dump_to_csv(self, db. collection, path):
        await self._dump_file(collection, path)

    async def _dump_file(self, db, collection, path, format):
        coll = self.client.get_database(db).get_collection(collection)
        docs = await coll.find({}, {'_id': 0}).to_list(length=INF)
        dl = ld_to_dl(docs)
        df = pandas.DataFrame(data=dl)
        if format == "csv":
            df.to_csv(path)

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
