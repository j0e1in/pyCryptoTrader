from setup import run

from pprint import pprint

from db import Datastore


def display(ds):
    """ Display datastore fields. """
    pass


def modify(ds):
    """ Modify datastore fields. """
    pass


def parse_args():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('task', type=str, help='Task to perform, display / modify')
    parser.add_argument('--name', type=str, help='Datastore name (HSET key)')
    parser.add_argument('--redis-host', type=str, help='Specify redis host')
    argv = parser.parse_args()

    return argv


async def main():
    argv = parse_args()

    ds_name = argv.name or ""  # enter datastore name here (HSET key)

    redis_host = argv.redis_host or None
    Datastore.update_redis(host=redis_host)
    ds = Datastore.create(f"{ds_name}")

    if argv.task == 'display':
        display(ds)
    elif argv.task == 'modify':
        modify(ds)
    else:
        argv.print_help()


if __name__ == '__main__':
    run(main)