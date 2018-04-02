from setup import run

import logging

from db import EXMongo, Datastore
from utils import config

logger = logging.getLogger('pyct')


def parse(ss):
    if not ss:
        return []

    parsed = ss.split('),(')

    pairs = []
    for p in parsed:
        pair = p.split(',')

        if len(pair) is not 2:
            raise ValueError("Invalid syntax")
        if '(' in pair[0]:
            pair[0] = pair[0][1:]
        if ')' in pair[1]:
            pair[1] = pair[1][:-1]

        pair[0] = pair[0].strip()
        pair[1] = pair[1].strip()
        pairs.append('-'.join(pair))

    return pairs


def registered(mongo, ue):
    coll = mongo.get_collection(
        config['database']['dbname_api'], 'account')
    uid, ex = ue.split('-')
    res = coll.find_one({'uid': uid, 'ex': ex})

    return True if res else False


def parse_args():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--add', type=str,
            help="Add trader, eg. --add=\"(uid1, ex),(uid2, ex)\"")
    parser.add_argument('--rm', type=str,
            help="Remove trader, eg. --rm=\"(uid1, ex),(uid2, ex)\"")
    argv = parser.parse_args()

    return argv


def main():
    argv = parse_args()
    mongo = EXMongo()
    ds = Datastore.create('trader_manager')
    uid_ex = ds.get('uid_ex', [])

    pairs = parse(argv.add)
    for ue in pairs:
        if ue in uid_ex:
            logger.info(f"{ue.split('-')} already exists")
        elif registered(mongo, ue):
            uid_ex.append(ue)
            logger.info(f"Added {ue.split('-')}")
        else:
            logger.warning(f"{ue.split('-')} is not registered")

    pairs = parse(argv.rm)
    for ue in pairs:
        if ue in uid_ex:
            uid_ex.remove(ue)
            logger.info(f"Removed {ue.split('-')}")
        else:
            logger.info(f"{ue.split('-')} does not exist")

    ds.uid_ex = uid_ex


if __name__ == '__main__':
    run(main)