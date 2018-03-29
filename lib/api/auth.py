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

    async def create_user(self, uid, email, phone, country_code):
        user = await loop.run_in_executor(None,
            self.authy_app.users.create,
            email, phone, country_code)

        if user.ok():
            if await self.user_exist(user.id):
                return False, f"User already exists"
            else:
                collname = f"authy_account"
                coll = self.mongo.get_collection(
                    self._config['database']['dbname_api'], collname)

                await coll.insert_one({
                    'uid': uid,
                    'authyid': user.id,
                    'email': email,
                    'phone': phone,
                    'country_code': country_code,
                })

            logger.info(f"Created authy user {user.id}/{email}")
            return True, ''
        else:
            logger.error(f"Creating authy user {user.id}/{email} failed: {user.errors()}")
            return False, user.errors()

    async def one_touch(self, authyid, message):

        async def save_transaction(request):
            coll = self.mongo.get_collection(
                self._config['database']['dbname_api'], "one_touch_history")

            await coll.insert_one(request)

        # Get email from database
        coll = self.mongo.get_collection(
            self._config['database']['dbname_api'], "authy_account")
        cred = await coll.find_one({'authyid': authyid})

        details = {
            'Username': cred['email'],
        }

        # Wrap kwargs to function because run_in_executor doesn't accept
        wrapped_func = functools.partial(
            self.authy_app.one_touch.send_request,
            cred['authyid'],
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

    async def user_exist(self, authyid):
        coll = self.mongo.get_collection(
            self.mongo.config['dbname_api'], "authy_account")
        res = await coll.find_one({'authyid': authyid})
        return False if not res else True

    async def get_authyid(self, uid):
        coll = self.mongo.get_collection(
            self.mongo.config['dbname_api'], "authy_account")
        res = await coll.find_one({'uid': uid})
        return res['authyid'] if res else ''
