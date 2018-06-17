from setup import run
from pprint import pprint
from time import sleep

import vm


def test_create_docker_node_with_cloud_config(mg):
    with open('../cloud-config-nodb.yml') as f:
        cloud_config = f.read()

    name = 'test-create-docker-node-with-cloud-config'
    size = mg.driver.list_sizes()[0]  # use smallest machine
    image = [
        img for img in mg.driver.list_images()
        if 'Docker' in img.name and '16.04' in img.name
    ][0]
    location = mg.driver.list_locations()[0]

    node = mg.driver.create_node(
        name=name,
        size=size,
        image=image,
        location=location,
        ex_user_data=cloud_config)

    node = mg.driver.wait_until_running([node]) # return list
    node = node[0] # return tuple
    node = node[0] # return updated Node instance
    print(f"Created a {mg.driver.name} node with IP {node.public_ips[0]}")
    return node


def test_destroy_node(mg, node):
    mg.driver.destroy_node(node)
    print(f'Destried {node.name}')


def main():
    cloud_provider = 'digitalocean'

    mg = vm.VMManger(
        cloud_provider=cloud_provider,
        token=vm.get_provider_token(cloud_provider))
    from ipdb import set_trace; set_trace()
    node = test_create_docker_node_with_cloud_config(mg)
    sleep(20)
    test_destroy_node(mg, node)


if __name__ == '__main__':
    run(main)