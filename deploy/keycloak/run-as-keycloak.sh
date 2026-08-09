#!/bin/sh
set -eu

source_directory=/run/secrets
target_directory=/run/pcbknowledge-keycloak-secrets

if [ "$(id -u)" -ne 0 ]; then
  echo "Keycloak secret staging must start as root" >&2
  exit 1
fi
if [ "$#" -eq 0 ]; then
  echo "Keycloak secret staging requires a command" >&2
  exit 1
fi

original_umask=$(umask)
umask 077
mkdir -p "$target_directory"
chown root:root "$target_directory"
chmod 711 "$target_directory"

found=false
for source_file in "$source_directory"/*; do
  if [ ! -f "$source_file" ]; then
    continue
  fi
  found=true
  name=${source_file##*/}
  target_file=$target_directory/$name
  temporary_file=$target_directory/.$name.tmp.$$
  if [ ! -s "$source_file" ]; then
    echo "required Keycloak secret is empty: $source_file" >&2
    exit 1
  fi
  cp "$source_file" "$temporary_file"
  chown root:0 "$temporary_file"
  chmod 440 "$temporary_file"
  mv -f "$temporary_file" "$target_file"
done
if [ "$found" != true ]; then
  echo "Keycloak secret staging found no granted secrets" >&2
  exit 1
fi

realm_file=$target_directory/pcbknowledge-realm.json
if [ -f "$realm_file" ]; then
  mkdir -p /opt/keycloak/data/import
  chown root:root /opt/keycloak/data/import
  chmod 755 /opt/keycloak/data/import
  import_file=/opt/keycloak/data/import/pcbknowledge-realm.json
  cp "$realm_file" "$import_file.tmp.$$"
  chown root:0 "$import_file.tmp.$$"
  chmod 440 "$import_file.tmp.$$"
  mv -f "$import_file.tmp.$$" "$import_file"
fi

export PCBKNOWLEDGE_SECRET_DIRECTORY=$target_directory
umask "$original_umask"
exec /usr/sbin/chroot --userspec=1000:0 / "$@"
