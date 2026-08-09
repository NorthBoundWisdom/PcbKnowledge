#!/bin/sh
set -eu

source_file=/run/secrets/grafana_admin_password
target_directory=/run/pcbknowledge-grafana-secrets
target_file=$target_directory/grafana_admin_password
temporary_file=$target_directory/.grafana_admin_password.tmp.$$

if [ "$(id -u)" -ne 0 ]; then
  echo "Grafana secret staging must start as root" >&2
  exit 1
fi
if [ ! -s "$source_file" ]; then
  echo "Grafana administrator password secret is required" >&2
  exit 1
fi

original_umask=$(umask)
umask 077
mkdir -p "$target_directory"
chown root:root "$target_directory"
chmod 711 "$target_directory"
cp "$source_file" "$temporary_file"
chown root:0 "$temporary_file"
chmod 440 "$temporary_file"
mv -f "$temporary_file" "$target_file"

export GF_SECURITY_ADMIN_PASSWORD__FILE=$target_file
umask "$original_umask"
exec su -s /bin/sh grafana -c 'exec /run.sh'
