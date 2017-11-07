import motor.motor_asyncio as motor
import logging

logger = logging.getLogger()


class Mongo():

    def __init__(self, *, host='localhost', port=27017, uri=None):
        if uri:
            logger.info(f"Connecting mongo client to {uri}")
            self.client = motor.AsyncIOMotorClient(uri)
        else:
            logger.info(f"Connecting mongo client to {host}:{port}")
            self.client = motor.AsyncIOMotorClient(host, port)

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
