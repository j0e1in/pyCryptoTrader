""" Delete nodes which names start with `prefix` when their cpu usage is low.
"""

from setup import run

import logging
import time

import vm

from utils import \
    config, \
    get_remote_cpu_usage

logger = logging.getLogger('pyct')

LOW_CPU_THRESH = 10 # (%)

def delete_node_on_low_cpu_usage(mg, prefix):
    nodes = mg.list_nodes()
    nodes = [n for n in nodes if n.name.startswith(prefix)]
    low_cpu_count = {node: 0 for node in nodes}

    while True:
        if not nodes:
            break

        to_remove = []

        for node in nodes:
            host = vm.node_host(node)
            cpu_usage = get_remote_cpu_usage(host)
            logger.info(f"{node.name} cpu usage: {cpu_usage}%")

            if cpu_usage < LOW_CPU_THRESH:
                low_cpu_count[node] += 1
            else:
                # reset if cpu usage is not low in a row
                low_cpu_count[node] = 0

            if low_cpu_count[node] > 5:
                logger.info(f"Deleting node: {node}")
                mg.driver.destroy_node(node)
                to_remove.append(node)

        # Remove deleted nodes
        for node in to_remove:
            nodes.remove(node)

        time.sleep(180)


def parse_args():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--prefix', type=str, help="Prefix of node's name")
    argv = parser.parse_args()

    return argv


def main():
    argv = parse_args()
    cloud_provider = config['vm']['cloud_provider']

    mg = vm.VMManger(
        cloud_provider=cloud_provider,
        token=vm.get_provider_token(cloud_provider))

    delete_node_on_low_cpu_usage(mg, prefix=argv.prefix)


if __name__ == '__main__':
    run(main)