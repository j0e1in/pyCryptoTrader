from authy.api import AuthyApiClient
from time import sleep

import logging

from utils import load_keys, config

logger = logging.getLogger('pytc')

class AuthyManager():

    def __init__(self, mongo, apikey=None, custom_config=None):
        self._config = custom_config if custom_config else config
        self.config = self._config['authy']
        self.mongo = mongo

        apikey = apikey if apikey else load_keys('AUTHY_APIKEY')
        self.authy_app = AuthyApiClient(apikey)

    async def create_user(self, email, phone, country_code):
        collname = f"authy_users"
        user = self.authy_app.users.create(email, phone, country_code)

        if user.ok():
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

            return True
        else:
            logger.error(f"Creating authy user {email} failed: {user.errors()}")
            return False

    async def one_touch(self, userid, message):

        async def save_transaction(request):
            collname = f"one_touch_history"
            coll = self.mongo.get_collection(
                self._config['database']['dbname_api'], collname)

            await coll.insert_one(request)

        collname = f"authy_users"
        coll = self.mongo.get_collection(
            self._config['database']['dbname_api'], collname)
        cred = await coll.find_one({'userid': userid}, {'_id': 0})

        details = {
            'Username': cred['email'],
        }

        res = self.authy_app.one_touch.send_request(userid, message,
            seconds_to_expire=self.config['seconds_to_expire'],
            details=details)
        # hidden_details=hidden_details,
        # logos=logos)

        if res.ok():
            uuid = res.get_uuid()
        else:
            logger.error(
                f"Error occured while sending request to {cred['email']}: {res.errors()}"
            )
            return False

        if res.ok():
            while True:
                res = self.authy_app.one_touch.get_approval_status(uuid)
                req = res.content['approval_request']
                status = req['status']

                # 'pending' | 'approved' | 'denied' | 'expired'
                if status == 'pending':
                    sleep(2)
                    continue
                elif status == 'approved':
                    await save_transaction(req)
                    return True
                elif status == 'denied' \
                or   status == 'expired':
                    await save_transaction(req)
                    return False
        else:
            logger.error(
                f"Error occured while getting status for {cred['email']}: {res.errors()}"
            )
            return False