REGION=sgp1

IMG=ubuntu-16-04-x64
# IMG=docker-16-04

# SIZE=s-6vcpu-16gb
SIZE=s-1vcpu-1gb

CLOUD_CONFIG=cloud-config-full.yml
# CLOUD_CONFIG=cloud-config-nodb.yml

TOKEN=$(cat ./private/digitalocean_token)
USER=user

docker-machine create \
--driver digitalocean \
--digitalocean-region $REGION \
--digitalocean-image $IMG \
--digitalocean-size $SIZE \
--digitalocean-access-token $TOKEN \
--digitalocean-ssh-user $USER \
--digitalocean-userdata $CLOUD_CONFIG \
--digitalocean-monitoring \
tune-snapshot

