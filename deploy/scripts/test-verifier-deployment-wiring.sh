#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/../.." && pwd)
cd "$repo_root"

command -v docker >/dev/null 2>&1 || {
  echo "docker is required for verifier deployment validation" >&2
  exit 1
}
command -v python3 >/dev/null 2>&1 || {
  echo "python3 is required for verifier deployment validation" >&2
  exit 1
}

"$script_dir/bootstrap-secrets.sh" >/dev/null

docker compose --profile tools config --format json |
  python3 -c '
import json
import sys

model = json.load(sys.stdin)
services = model["services"]
postgres = services["postgres"]
assert postgres["entrypoint"] == ["/bin/sh", "/opt/pcbknowledge/start-postgres.sh"]
assert postgres["environment"]["POSTGRES_PASSWORD_FILE"] == (
    "/run/pcbknowledge-postgres-secrets/postgres_password"
)

keycloak_runner = [
    "/bin/sh",
    "/opt/pcbknowledge/run-as-keycloak.sh",
    "/bin/sh",
    "/opt/pcbknowledge/start-keycloak.sh",
]
assert services["keycloak"]["user"] == "0:0"
assert services["keycloak"]["entrypoint"] == keycloak_runner
assert services["keycloak-reconcile"]["user"] == "0:0"
assert services["local-curator-keycloak"]["user"] == "0:0"
assert services["grafana"]["user"] == "0:0"
assert services["grafana"]["entrypoint"] == [
    "/bin/sh", "/opt/pcbknowledge/start-grafana.sh"
]

verifier = services["verifier"]
assert verifier["command"] == [
    "python", "-m", "pcbknowledge.document.verifier", "serve"
]
assert verifier["environment"]["PCBKNOWLEDGE_DATABASE_USERNAME"] == "pcbknowledge_verifier"
assert verifier["environment"]["PCBKNOWLEDGE_S3_ACCESS_MODE"] == "verifier"
assert verifier["depends_on"]["postgres"]["condition"] == "service_healthy"
assert verifier["depends_on"]["seaweedfs"]["condition"] == "service_healthy"
assert verifier["healthcheck"]["test"] == [
    "CMD",
    "/bin/sh",
    "/usr/local/bin/pcbknowledge-backend-entrypoint",
    "python",
    "-m",
    "pcbknowledge.document.verifier",
    "health-check",
]
verifier_secrets = {
    (item["source"], item.get("target", item["source"]).rsplit("/", 1)[-1])
    for item in verifier["secrets"]
}
assert verifier_secrets == {
    ("verifier_db_password", "verifier_db_password"),
    ("seaweedfs_verifier_access_key", "seaweedfs_access_key"),
    ("seaweedfs_verifier_secret_key", "seaweedfs_secret_key"),
}
assert {item["source"] for item in services["seaweedfs"]["secrets"]} >= {
    "seaweedfs_verifier_access_key", "seaweedfs_verifier_secret_key"
}
assert {item["source"] for item in services["postgres-reconcile"]["secrets"]} >= {
    "verifier_db_password"
}
'

python3 - <<'PY'
import re
import stat
from pathlib import Path

secret_paths = {
    name: Path("deploy/secrets") / name
    for name in (
        "verifier_db_password",
        "seaweedfs_verifier_access_key",
        "seaweedfs_verifier_secret_key",
    )
}
values: dict[str, str] = {}
for name, path in secret_paths.items():
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    value = path.read_text(encoding="utf-8").strip()
    assert re.fullmatch(r"[0-9a-f]+", value)
    values[name] = value

for verifier_name, other_names in {
    "seaweedfs_verifier_access_key": (
        "seaweedfs_access_key",
        "seaweedfs_admin_access_key",
        "seaweedfs_worker_access_key",
    ),
    "seaweedfs_verifier_secret_key": (
        "seaweedfs_secret_key",
        "seaweedfs_admin_secret_key",
        "seaweedfs_worker_secret_key",
    ),
}.items():
    for other_name in other_names:
        other_value = (Path("deploy/secrets") / other_name).read_text(encoding="utf-8").strip()
        assert values[verifier_name] != other_value

seaweedfs_script = Path("deploy/seaweedfs/start-seaweedfs.sh").read_text(encoding="utf-8")
verifier_identity = next(
    line for line in seaweedfs_script.splitlines() if '"pcbknowledge-verifier"' in line
)
assert verifier_identity.count('"Read:') == 2
assert verifier_identity.count('"Write:') == 2
assert verifier_identity.count('$staging_bucket') == 2
assert verifier_identity.count('$content_bucket') == 2
assert "Admin" not in verifier_identity
assert "List:" not in verifier_identity
assert (
    "-s3.allowedOrigins=http://localhost:8080,http://localhost:18080,"
    "http://localhost:5173,http://127.0.0.1:4173"
) in seaweedfs_script
assert "-s3.allowedOrigins=*" not in seaweedfs_script
assert "-volume.max=32" in seaweedfs_script

role_script = Path("deploy/postgres/reconcile-application-role.sh").read_text(encoding="utf-8")
assert "ALTER ROLE pcbknowledge_verifier" in role_script
assert "NOREPLICATION NOBYPASSRLS" in role_script
assert "REVOKE %I FROM pcbknowledge_verifier" in role_script
assert "REVOKE pcbknowledge_verifier FROM %I" in role_script

entrypoint = Path("deploy/docker/backend-entrypoint.sh").read_text(encoding="utf-8")
assert "pcbknowledge_verifier)" in entrypoint
assert '"$secret_directory/verifier_db_password"' in entrypoint
assert "--reuid=pcbknowledge" in entrypoint
assert "PATH=$trusted_path" in entrypoint
assert "PATH=$application_path" in entrypoint

dockerfile = Path("deploy/docker/backend.Dockerfile").read_text(encoding="utf-8")
runtime = dockerfile.split("FROM application AS runtime", 1)[1]
assert "USER root" in runtime
assert "/usr/local/bin/pcbknowledge-backend-entrypoint" in runtime
assert "--mode=0555" in runtime

postgres_start = Path("deploy/postgres/start-postgres.sh").read_text(encoding="utf-8")
assert "chown root:postgres" in postgres_start
assert "exec docker-entrypoint.sh" in postgres_start

keycloak_runner = Path("deploy/keycloak/run-as-keycloak.sh").read_text(encoding="utf-8")
assert "chmod 440" in keycloak_runner
assert "chroot --userspec=1000:0" in keycloak_runner

grafana_start = Path("deploy/observability/grafana/start-grafana.sh").read_text(
    encoding="utf-8"
)
assert "chmod 440" in grafana_start
assert "su -s /bin/sh grafana" in grafana_start
PY

echo "Verifier Compose, secret, database-role, entrypoint, and S3 policy wiring is exact."
