from setup import run

from pprint import pformat
import copy
import logging
import os
import pipes
import subprocess
import multiprocessing
import sys
import time
import tempfile

import vm

from utils import \
    config, \
    remote_exists, \
    rsym

logger = logging.getLogger('pyct')


def deploy_optimization(node):
    """ Run deployment script in background and return the subprocess. """
    working_dir = os.path.dirname(os.getcwd())
    ip = node.public_ips[0]
    host = f"{config['vm']['remote_user']}@{ip}"
    symbol = node_symbol(node)
    deploy_script_path = './scripts/system/remote_deploy_docker_stack.sh'
    cmd = [deploy_script_path, host, 'optimize', '--pull', f'--symbol={symbol}']

    logger.info(f"Start process: {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd,
        cwd=working_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    return proc


def cloud_init_status(node):
    """ Check if cloud-init is finished or not. """
    ip = node.public_ips[0]
    host = f"{config['vm']['remote_user']}@{ip}"
    ssh_options = '-o StrictHostKeyChecking=no'  # ignore ssh authenticy check

    try:
        # Check if `boot-finished` exists on remote
        # (cloud-init creates this file when it's done)
        target_file = '/var/lib/cloud/instance/boot-finished'
        if remote_exists(host, target_file, ssh_options):
            logger.debug('cloud-init finished')
            return 'finished'
        else:
            logger.debug('cloud-init not finished')
            return 'running'
    except RuntimeError:
        logger.debug('ssh failed')
        return 'ssh failed'


def create_node(mg, sym):
    with open('../cloud-config-nodb.yml') as f:
        cloud_config = f.read()

    options = dict(
        name=f"optimize-{'-'.join(sym.split('/'))}",
        size=[s for s in mg.list_sizes() if 's-6vcpu-16gb' == s.name][0],
        location=[loc for loc in mg.list_locations() if loc.id == 'sgp1'][0],
        image=[
            img for img in mg.list_images()
            if 'Docker' in img.name and '16.04' in img.name
        ][0])

    logger.info(
        f"Creating {mg.driver.name} node with settings:\n{pformat(options)}")

    node = mg.driver.create_node(**options, ex_user_data=cloud_config)

    return node


def node_symbol(node):
    """ Restore symbol from node's name. """
    return '/'.join(node.name.split('-')[1:])


def get_docker_log(node, service):
    ip = node.public_ips[0]
    host = f"{config['vm']['remote_user']}@{ip}"
    cmd = ['ssh', host, 'docker', 'service', 'logs', service]
    output = subprocess.check_output(cmd)
    return output


def main():
    cloud_provider = config['vm']['cloud_provider']

    mg = vm.VMManger(
        cloud_provider=cloud_provider,
        token=vm.get_provider_token(cloud_provider))

    symbols_to_optimize = [
        # "BTC/USD",
        # "BCH/USD",
        # "ETH/USD",
        # "EOS/USD",
        # "XRP/USD",
        # "ETC/USD",

        # "OMG/USD",
        # "DASH/USD",
        # "IOTA/USD",
        # "LTC/USD",
        # "NEO/USD",
        # "XMR/USD",
        # "ZEC/USD",

        # "BTG/USD",
        # "EDO/USD",
        # "ETP/USD",
        # "SAN/USD",
    ]

    nodes = []
    for sym in symbols_to_optimize:
        nodes.append(create_node(mg, sym))

    nodes = mg.driver.wait_until_running(nodes)
    nodes_copy = [node for node, _ in nodes]

    logger.info(f"Wait for 120 sec...")
    time.sleep(120)

    # Wait for node's cloud init to finish and then deploy
    # the symbol's optimization process
    while True:
        if not nodes:
            break

        deployed = []
        deploy_procs = []

        for node, ip in nodes:
            sym = node_symbol(node)
            if cloud_init_status(node) == 'finished':
                logger.info(f"Deploying {sym} optimization to {node.name} @ {ip[0]}")
                p = deploy_optimization(node)

                if not p:
                    logger.error(f"Deployment failed: {node.name} @ {ip}")
                else:
                    deploy_procs.append(p)

                deployed.append((node, ip))
            time.sleep(30)

        for it in deployed:
            nodes.remove(it)

    # Read output of deployment process
    logger.info(f"Waiting for deployment processes to complete")
    print(deploy_procs)
    for p in deploy_procs:
        # for line in p.stdout:
        #     sys.stdout.write(line.decode('utf-8'))

        output, err = p.communicate(timeout=60)

        if err: # failed
            err = err.decode('utf-8')
            msg = f"[Error Message]\n{err}"
            logger.info(msg)

    logger.info(f"Wait for 60 sec...")
    time.sleep(60)

    for node in nodes_copy:
        logger.info(f"{node_symbol(node)} log:\n{get_docker_log(node, service='optimize_optimize')}")


if __name__ == '__main__':
    run(main)
