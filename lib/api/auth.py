from authy.api import AuthyApiClient
from time import sleep

import asyncio
import functools
import logging

from utils import load_keys, config

logger = logging.getLogger('pytc')
loop = asyncio.get_event_loop()

class AuthyManager():

    def __init__(self, mongo, apikey=None, custom_config=None):
        self._config = custom_config if custom_config else config
        self.config = self._config['authy']
        self.mongo = mongo

        apikey = apikey if apikey else load_keys()['AUTHY_APIKEY']
        self.authy_app = AuthyApiClient(apikey)

    async def create_user(self, email, phone, country_code):
        user = await loop.run_in_executor(None,
            self.authy_app.users.create,
            email, phone, country_code)

        if user.ok():
            collname = f"authy_users"
            coll = self.mongo.get_collection(
                self._config['database']['dbname_api'], collname)

            await coll.update_one(
                    {'userid': user.id},
                    {'$set': {
                        'userid': user.id,
                        'email': email,
                        'phone': phone,
                        'country_code': country_code,
                    }}, upsert=True)

            return True, ''
        else:
            logger.error(f"Creating authy user {email} failed: {user.errors()}")
            return False, user.errors()

    async def one_touch(self, userid, message):

        async def save_transaction(request):
            collname = f"one_touch_history"
            coll = self.mongo.get_collection(
                self._config['database']['dbname_api'], collname)

            await coll.insert_one(request)

        # Get email from database
        collname = f"authy_users"
        coll = self.mongo.get_collection(
            self._config['database']['dbname_api'], collname)
        cred = await coll.find_one({'userid': userid}, {'_id': 0})

        details = {
            'Username': cred['email'],
        }

        # Wrap kwargs to function because run_in_executor doesn't accept
        wrapped_func = functools.partial(
            self.authy_app.one_touch.send_request,
            userid,
            message,
            seconds_to_expire=self.config['seconds_to_expire'],
            details=details)
        # hidden_details=hidden_details)

        res = await loop.run_in_executor(None, wrapped_func)

        if res.ok():
            uuid = res.get_uuid()
        else:
            logger.error(
                f"Error occured while sending request to {cred['email']}: {res.errors()}"
            )
            return False, ''

        if res.ok():
            while True:
                res = await loop.run_in_executor(None,
                    self.authy_app.one_touch.get_approval_status, uuid)
                req = res.content['approval_request']
                status = req['status']

                # 'pending' | 'approved' | 'denied' | 'expired'
                if status == 'pending':
                    sleep(2)
                    continue
                elif status == 'approved':
                    await save_transaction(req)
                    return True, status
                elif status == 'denied' \
                or   status == 'expired':
                    await save_transaction(req)
                    return False, status
        else:
            logger.error(
                f"Error occured while getting status for {cred['email']}: {res.errors()}"
            )
            return False, ''

    def get_userid(self, uid):
        keys = load_keys()

        if uid not in keys:
            return ''

        return keys[uid]['authy_userid']

    async def user_exist(self, userid):
        collname = f"authy_users"
        coll = self.mongo.get_collection(
            self._config['database']['dbname_api'], collname)
        res = await coll.find_one({'userid': userid})
        return False if not res else True