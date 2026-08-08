#!/bin/sh
set -eu

read_secret() {
  if [ ! -s "$1" ]; then
    echo "required secret is missing or empty: $1" >&2
    exit 1
  fi
  tr -d '\r\n' <"$1"
}

api_access_key=$(read_secret /run/secrets/seaweedfs_access_key)
api_secret_key=$(read_secret /run/secrets/seaweedfs_secret_key)
admin_access_key=$(read_secret /run/secrets/seaweedfs_admin_access_key)
admin_secret_key=$(read_secret /run/secrets/seaweedfs_admin_secret_key)
worker_access_key=$(read_secret /run/secrets/seaweedfs_worker_access_key)
worker_secret_key=$(read_secret /run/secrets/seaweedfs_worker_secret_key)
content_bucket=${PCBKNOWLEDGE_S3_BUCKET:-pcbknowledge-assets}
staging_bucket=${PCBKNOWLEDGE_S3_STAGING_BUCKET:-pcbknowledge-staging}
runtime_config=/tmp/pcbknowledge-s3.json

validate_bucket() {
  case "$1" in
    ''|.*|*.|*[!a-z0-9.-]*)
      echo "invalid SeaweedFS bucket name" >&2
      exit 1
      ;;
  esac
  if [ "${#1}" -lt 3 ] || [ "${#1}" -gt 63 ]; then
    echo "invalid SeaweedFS bucket name length" >&2
    exit 1
  fi
}
validate_bucket "$content_bucket"
validate_bucket "$staging_bucket"
if [ "$content_bucket" = "$staging_bucket" ]; then
  echo "permanent and staging SeaweedFS buckets must differ" >&2
  exit 1
fi

printf '%s\n' \
  '{"identities":[' \
  '{"name":"pcbknowledge-admin","credentials":[{"accessKey":"'"$admin_access_key"'","secretKey":"'"$admin_secret_key"'"}],"actions":["Admin"]},' \
  '{"name":"pcbknowledge-api","credentials":[{"accessKey":"'"$api_access_key"'","secretKey":"'"$api_secret_key"'"}],"actions":["Read:'"$content_bucket"'","List:'"$content_bucket"'","Read:'"$staging_bucket"'","Write:'"$staging_bucket"'","List:'"$staging_bucket"'"]},' \
  '{"name":"pcbknowledge-worker","credentials":[{"accessKey":"'"$worker_access_key"'","secretKey":"'"$worker_secret_key"'"}],"actions":["Write:'"$staging_bucket"'"]}' \
  ']}' \
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
