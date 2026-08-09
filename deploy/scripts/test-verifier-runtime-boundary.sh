#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/../.." && pwd)
cd "$repo_root"

for service in postgres seaweedfs; do
  if ! docker compose ps --status running --services | grep -Fxq "$service"; then
    echo "a running $service service is required" >&2
    exit 1
  fi
done

probe_suffix=$(openssl rand -hex 12)
api_probe_key=boundary-probes/api-denied-$probe_suffix
worker_probe_key=boundary-probes/worker-denied-$probe_suffix
verifier_content_key=boundary-probes/verifier-content-$probe_suffix
verifier_staging_key=boundary-probes/verifier-staging-$probe_suffix
verifier_denied_bucket=pcbknowledge-verifier-denied-$probe_suffix

cleanup_probe_objects() {
  PCBKNOWLEDGE_TEST_API_KEY=$api_probe_key \
  PCBKNOWLEDGE_TEST_WORKER_KEY=$worker_probe_key \
  PCBKNOWLEDGE_TEST_VERIFIER_CONTENT_KEY=$verifier_content_key \
  PCBKNOWLEDGE_TEST_VERIFIER_STAGING_KEY=$verifier_staging_key \
  PCBKNOWLEDGE_TEST_VERIFIER_DENIED_BUCKET=$verifier_denied_bucket \
    docker compose --profile tools run --rm --no-deps -T \
    -e PCBKNOWLEDGE_TEST_API_KEY \
    -e PCBKNOWLEDGE_TEST_WORKER_KEY \
    -e PCBKNOWLEDGE_TEST_VERIFIER_CONTENT_KEY \
    -e PCBKNOWLEDGE_TEST_VERIFIER_STAGING_KEY \
    -e PCBKNOWLEDGE_TEST_VERIFIER_DENIED_BUCKET \
    storage-init python - <<'PY' >/dev/null 2>&1 || true
import os

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

client = boto3.client(
    "s3",
    endpoint_url=os.environ["PCBKNOWLEDGE_S3_ENDPOINT_URL"],
    region_name=os.environ["PCBKNOWLEDGE_S3_REGION"],
    config=Config(s3={"addressing_style": "path"}),
)
content_bucket = os.environ["PCBKNOWLEDGE_S3_BUCKET"]
staging_bucket = os.environ["PCBKNOWLEDGE_S3_STAGING_BUCKET"]
for key in (
    os.environ["PCBKNOWLEDGE_TEST_API_KEY"],
    os.environ["PCBKNOWLEDGE_TEST_WORKER_KEY"],
    os.environ["PCBKNOWLEDGE_TEST_VERIFIER_CONTENT_KEY"],
):
    client.delete_object(Bucket=content_bucket, Key=key)
client.delete_object(
    Bucket=staging_bucket,
    Key=os.environ["PCBKNOWLEDGE_TEST_VERIFIER_STAGING_KEY"],
)
try:
    client.delete_bucket(Bucket=os.environ["PCBKNOWLEDGE_TEST_VERIFIER_DENIED_BUCKET"])
except ClientError as error:
    if error.response.get("Error", {}).get("Code") not in {"404", "NoSuchBucket"}:
        raise
PY
}
trap cleanup_probe_objects EXIT HUP INT TERM

PCBKNOWLEDGE_TEST_CONTENT_KEY=$verifier_content_key \
PCBKNOWLEDGE_TEST_STAGING_KEY=$verifier_staging_key \
PCBKNOWLEDGE_TEST_DENIED_BUCKET=$verifier_denied_bucket \
  docker compose run --rm --no-deps -T \
  -e PCBKNOWLEDGE_TEST_CONTENT_KEY \
  -e PCBKNOWLEDGE_TEST_STAGING_KEY \
  -e PCBKNOWLEDGE_TEST_DENIED_BUCKET \
  verifier python - <<'PY'
import os

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from sqlalchemy import create_engine, text

engine = create_engine(os.environ["PCBKNOWLEDGE_DATABASE_DSN"])
with engine.connect() as connection:
    identity = connection.execute(
        text(
            "SELECT session_user, current_user, rolsuper, rolcreatedb, "
            "rolcreaterole, rolinherit, rolreplication, rolbypassrls "
            "FROM pg_catalog.pg_roles WHERE rolname = current_user"
        )
    ).one()
    assert identity == (
        "pcbknowledge_verifier",
        "pcbknowledge_verifier",
        False,
        False,
        False,
        False,
        False,
        False,
    )
    memberships = connection.execute(
        text(
            "SELECT count(*) FROM pg_catalog.pg_auth_members AS membership "
            "JOIN pg_catalog.pg_roles AS member_role "
            "ON member_role.oid = membership.member "
            "JOIN pg_catalog.pg_roles AS granted_role "
            "ON granted_role.oid = membership.roleid "
            "WHERE member_role.rolname = 'pcbknowledge_verifier' "
            "OR granted_role.rolname = 'pcbknowledge_verifier'"
        )
    ).scalar_one()
    assert memberships == 0
engine.dispose()

client = boto3.client(
    "s3",
    endpoint_url=os.environ["PCBKNOWLEDGE_S3_ENDPOINT_URL"],
    region_name=os.environ["PCBKNOWLEDGE_S3_REGION"],
    config=Config(s3={"addressing_style": "path"}),
)
content_bucket = os.environ["PCBKNOWLEDGE_S3_BUCKET"]
staging_bucket = os.environ["PCBKNOWLEDGE_S3_STAGING_BUCKET"]
payload = b"pcbknowledge-verifier-boundary-probe"
for bucket, key in (
    (content_bucket, os.environ["PCBKNOWLEDGE_TEST_CONTENT_KEY"]),
    (staging_bucket, os.environ["PCBKNOWLEDGE_TEST_STAGING_KEY"]),
):
    client.put_object(Bucket=bucket, Key=key, Body=payload)
    response = client.get_object(Bucket=bucket, Key=key)
    assert response["Body"].read() == payload

for operation in (
    lambda: client.list_objects_v2(Bucket=content_bucket, MaxKeys=1),
    lambda: client.list_objects_v2(Bucket=staging_bucket, MaxKeys=1),
):
    try:
        operation()
    except ClientError as exc:
        assert exc.response["ResponseMetadata"]["HTTPStatusCode"] == 403
    else:
        raise AssertionError("verifier object listing was not denied")

# SeaweedFS 3.85 returns 200 for ListBuckets and filters the result through
# per-bucket List actions. The verifier has no such action, so no bucket name
# may cross this boundary even though the operation itself is successful.
assert client.list_buckets().get("Buckets", []) == []

try:
    client.create_bucket(Bucket=os.environ["PCBKNOWLEDGE_TEST_DENIED_BUCKET"])
except ClientError as exc:
    assert exc.response["ResponseMetadata"]["HTTPStatusCode"] == 403
else:
    raise AssertionError("verifier unexpectedly performed an Admin bucket operation")
PY

for denied_service in api worker; do
  case "$denied_service" in
    api) denied_key=$api_probe_key ;;
    worker) denied_key=$worker_probe_key ;;
  esac
  PCBKNOWLEDGE_TEST_DENIED_KEY=$denied_key \
    docker compose run --rm --no-deps -T \
    -e PCBKNOWLEDGE_TEST_DENIED_KEY \
    "$denied_service" python - <<'PY'
import os

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

client = boto3.client(
    "s3",
    endpoint_url=os.environ["PCBKNOWLEDGE_S3_ENDPOINT_URL"],
    region_name=os.environ["PCBKNOWLEDGE_S3_REGION"],
    config=Config(s3={"addressing_style": "path"}),
)
try:
    client.put_object(
        Bucket=os.environ["PCBKNOWLEDGE_S3_BUCKET"],
        Key=os.environ["PCBKNOWLEDGE_TEST_DENIED_KEY"],
        Body=b"must-not-be-written",
    )
except ClientError as exc:
    assert exc.response["ResponseMetadata"]["HTTPStatusCode"] == 403
else:
    raise AssertionError("runtime principal unexpectedly wrote permanent content")
PY
done

cleanup_probe_objects
trap - EXIT HUP INT TERM

echo "Verifier DB isolation and S3 allow/deny boundaries passed on real services."
