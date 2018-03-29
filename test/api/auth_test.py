from setup import run


from pprint import pprint

from api import AuthyManager
from db import EXMongo
from trading.trader import SingleEXTrader
from utils import load_json


async def test_create_user(authy, cred):
    print('-- create_user --')
    res = await authy.create_user(
        cred['email'],
        cred['phone'],
        cred['country_code'],
    )
    pprint(res)


async def test_one_touch(authy, cred):
    print('-- one_touch --')
    res = await authy.one_touch(cred['"authy"'], "Test ask approval")
    pprint(res)


async def main():

    mongo = EXMongo()
    authy = AuthyManager(mongo)
    credentials = load_json('../private/data.json')['authy']

    # await test_create_user(authy, credentials)
    # await test_one_touch(authy, credentials)


if __name__ == "__main__":
    run(main)