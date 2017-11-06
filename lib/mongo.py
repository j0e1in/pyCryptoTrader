import motor.motor_asyncio as motor


class Mongo():

    def __init__(self, *, host='localhost', port=27017, uri=None):
        if uri:
            self.client = motor.AsyncIOMotorClient(uri)
        else:
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
