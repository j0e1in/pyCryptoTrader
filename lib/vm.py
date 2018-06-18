import libcloud
import json

from utils import config


def get_provider_type(provider):
    if provider == 'digitalocean':
        return libcloud.compute.types.Provider.DIGITAL_OCEAN
    else:
        raise ValueError(f"Cloud provider `{provider}` is not supported")


def get_provider_token(provider):
    with open(config['vm']['provider_token_file']) as f:
        return json.load(f)[provider]


def node_symbol(node):
    """ Restore symbol from node's name. """
    return '/'.join(node.name.split('-')[1:])


def node_host(node):
    ip = node.public_ips[0]
    host = f"{config['vm']['remote_user']}@{ip}"
    return host


class VMManger:
    def __init__(self, cloud_provider, username=None, token=None):
        cls = libcloud.compute.providers.get_driver(
            get_provider_type(cloud_provider))

        driver_args = []
        if username:
            driver_args.append(username)
        if token:
            driver_args.append(token)

        self.driver = cls(*driver_args)

    def list_images(self):
        return self.driver.list_images()

    def list_sizes(self):
        return self.driver.list_sizes()

    def list_nodes(self):
        return self.driver.list_nodes()

    def list_locations(self):
        return self.driver.list_locations()