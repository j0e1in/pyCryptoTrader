from utils import \
    INF, \
    utc_now

async def record_account_value(trader):
    """ Save account value to db. """
    await trader.ex.update_wallet()
    mongo = trader.mongo
    db = mongo.config['dbname_history']
    coll = mongo.get_collection(db, 'account_value')
    last_value = (await coll.find({
        'uid': trader.uid,
        'ex': trader.ex.exname,
    }).sort([('datetime', -1)]).limit(1).to_list(length=INF))

    last_value = last_value[0]['value'] if last_value else 0
    cur_value = await trader.ex.calc_account_value(include_pl=False)

    if cur_value != last_value:
        await coll.insert_one({
            'uid': trader.uid,
            'ex': trader.ex.exname,
            'value': cur_value,
            'datetime': utc_now()
        })