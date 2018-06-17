#!/bin/bash

# Create a instance

SYMBOLS=ETH/USD

NAME=()
TAGS=()
while IFS=',' read -ra PLAIN_SYMBOLS; do
  for i in "${PLAIN_SYMBOLS[@]}"; do
      IFS='/' read -ra CURRENCY <<< "$i"
      NAME=("${NAME[@]}" "${CURRENCY[0]}")
      TAGS=("${TAGS[@]}" "${CURRENCY[@]}")
  done

  IFS=$'-'; # delimiter for ${NAME[*]}

  docker-machine create \
  --driver digitalocean \
  --digitalocean-access-token $(cat private/digitalocean_token) \
  --digitalocean-image docker-16-04 \
  --digitalocean-region sgp1 \
  --digitalocean-size s-6vcpu-16gb \
  --digitalocean-tags "${TAGS[*]}" \
  --digitalocean-monitoring \
  --digitalocean-userdata "./cloud-config-nodb.yml" \
  "optimization-${NAME[*]}"

done <<< "$SYMBOLS"

sleep 180

