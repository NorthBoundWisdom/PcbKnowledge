#!/bin/sh
set -eu

read_secret() {
  if [ ! -s "$1" ]; then
    echo "required secret is missing or empty: $1" >&2
    exit 1
  fi
  tr -d '\r\n' <"$1"
}

access_key=$(read_secret /run/secrets/seaweedfs_access_key)
secret_key=$(read_secret /run/secrets/seaweedfs_secret_key)
runtime_config=/tmp/pcbknowledge-s3.json

printf '%s\n' \
  '{"identities":[{"name":"pcbknowledge","credentials":[{"accessKey":"'"$access_key"'","secretKey":"'"$secret_key"'"}],"actions":["Admin","Read","Write","List","Tagging"]}]}' \
  >"$runtime_config"
chmod 600 "$runtime_config"

exec /usr/bin/weed server \
  -dir=/data \
  -master.port=9333 \
  -volume.port=8080 \
  -filer \
  -filer.port=8888 \
  -s3 \
  -s3.port=8333 \
  -s3.config="$runtime_config"
