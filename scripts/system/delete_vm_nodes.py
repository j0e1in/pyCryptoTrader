from setup import run

import logging

import vm

from utils import config

logger = logging.getLogger('pyct')

def delete_nodes_by_name_prefix(mg, prefix):
    if not isinstance(prefix, str):
        raise ValueError('Prefix must be str')

    nodes = mg.list_nodes()
    for node in nodes:
        if node.name.startswith(prefix):
            logger.info(f"Deleting {node}")
            mg.driver.destroy_node(node)


def delete_nodes_by_ip(mg, ips):
    if not isinstance(ips, list):
        raise ValueError('ips must be list')

    nodes = mg.list_nodes()
    for node in nodes:
        for ip in ips:
            if ip in node.public_ips:
                logger.info(f"Deleting {node}")
                mg.driver.destroy_node(node)


def parse_args():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--prefix', type=str, help="Prefix of node's name")
    parser.add_argument('--ips', type=str, nargs='+', help="Nodes' IPs")
    argv = parser.parse_args()

    return argv


def main():
    argv = parse_args()

    cloud_provider = config['vm']['cloud_provider']

    mg = vm.VMManger(
        cloud_provider=cloud_provider,
        token=vm.get_provider_token(cloud_provider))

    if argv.prefix:
        delete_nodes_by_name_prefix(mg, argv.prefix)

    if argv.ips:
        delete_nodes_by_ip(mg, argv.ips)


if __name__ == '__main__':
    run(main)