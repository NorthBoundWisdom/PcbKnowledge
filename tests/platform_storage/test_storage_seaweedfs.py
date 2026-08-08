"""Real SeaweedFS S3 presign, integrity, and anonymous-access tests."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid7

import boto3  # type: ignore[import-untyped]
import pytest
from botocore.config import Config  # type: ignore[import-untyped]
from botocore.exceptions import ClientError  # type: ignore[import-untyped]

from pcbknowledge.platform.storage import (
    ObjectIntegrityError,
    ObjectStoreUnavailableError,
    SeaweedFsS3Adapter,
)
from pcbknowledge.platform.storage.adapter import StagingCleanupIntent


@dataclass(frozen=True, slots=True)
class S3Environment:
    endpoint: str
    public_endpoint: str
    access_key: str
    secret_key: str
    admin_access_key: str
    admin_secret_key: str
    worker_access_key: str
    worker_secret_key: str
    bucket: str
    staging_bucket: str


def require_s3_environment() -> S3Environment:
    names = {
        "endpoint": "PCBKNOWLEDGE_M1_S3_ENDPOINT_URL",
        "public_endpoint": "PCBKNOWLEDGE_M1_S3_PUBLIC_ENDPOINT_URL",
        "access_key": "PCBKNOWLEDGE_M1_S3_ACCESS_KEY",
        "secret_key": "PCBKNOWLEDGE_M1_S3_SECRET_KEY",
        "admin_access_key": "PCBKNOWLEDGE_M1_S3_ADMIN_ACCESS_KEY",
        "admin_secret_key": "PCBKNOWLEDGE_M1_S3_ADMIN_SECRET_KEY",
        "worker_access_key": "PCBKNOWLEDGE_M1_S3_WORKER_ACCESS_KEY",
        "worker_secret_key": "PCBKNOWLEDGE_M1_S3_WORKER_SECRET_KEY",
        "bucket": "PCBKNOWLEDGE_M1_S3_BUCKET",
        "staging_bucket": "PCBKNOWLEDGE_M1_S3_STAGING_BUCKET",
    }
    values = {field: os.environ.get(name) for field, name in names.items()}
    if any(value is None for value in values.values()):
        pytest.skip("set explicit PCBKNOWLEDGE_M1_S3_* variables for SeaweedFS tests")
    return S3Environment(**values)  # type: ignore[arg-type]


def test_presign_put_get_integrity_deferred_cleanup_and_anonymous_deny() -> None:
    environment = require_s3_environment()
    admin = boto3.client(
        "s3",
        endpoint_url=environment.endpoint,
        aws_access_key_id=environment.admin_access_key,
        aws_secret_access_key=environment.admin_secret_key,
        region_name="us-east-1",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    for bucket in (environment.bucket, environment.staging_bucket):
        try:
            admin.create_bucket(Bucket=bucket)
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") not in {
                "BucketAlreadyExists",
                "BucketAlreadyOwnedByYou",
            }:
                raise
    client = boto3.client(
        "s3",
        endpoint_url=environment.endpoint,
        aws_access_key_id=environment.access_key,
        aws_secret_access_key=environment.secret_key,
        region_name="us-east-1",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    adapter = SeaweedFsS3Adapter.from_credentials(
        internal_endpoint_url=environment.endpoint,
        public_endpoint_url=environment.public_endpoint,
        access_key_id=environment.access_key,
        secret_access_key=environment.secret_key,
        bucket=environment.bucket,
        staging_bucket=environment.staging_bucket,
    )
    promoter = SeaweedFsS3Adapter.from_credentials(
        internal_endpoint_url=environment.endpoint,
        public_endpoint_url=environment.public_endpoint,
        access_key_id=environment.admin_access_key,
        secret_access_key=environment.admin_secret_key,
        bucket=environment.bucket,
        staging_bucket=environment.staging_bucket,
        allow_content_write=True,
    )
    organization_id = uuid7()
    upload_id = uuid7()
    content = b"PcbKnowledge M1 SeaweedFS integration evidence"
    digest = hashlib.sha256(content).hexdigest()

    try:
        upload = adapter.presign_staging_put(
            organization_id=organization_id,
            upload_id=upload_id,
            media_type="application/pdf",
            expected_byte_size=len(content),
        )
        request = Request(
            upload.url,
            data=content,
            headers=dict(upload.headers),
            method="PUT",
        )
        with urlopen(request, timeout=10) as response:
            assert response.status in {200, 201}

        snapshot = adapter.snapshot_staging(
            organization_id=organization_id,
            upload_id=upload_id,
            expected_sha256=digest,
            expected_byte_size=len(content),
        )
        with pytest.raises(ObjectStoreUnavailableError):
            adapter.promote_snapshot(snapshot)
        reference = promoter.promote_snapshot(snapshot)
        inspection = snapshot.inspection
        adapter.cleanup_snapshot(snapshot)
        assert inspection.sha256 == digest
        assert inspection.byte_size == len(content)

        # Promotion must retain staging until the committed outbox event runs.
        assert client.head_object(
            Bucket=environment.staging_bucket,
            Key=f"organizations/{organization_id}/staging/{upload_id}",
        )["ContentLength"] == len(content)

        download = adapter.presign_download(reference)
        with urlopen(download.url, timeout=10) as response:
            assert response.read() == content

        anonymous_url = (
            f"{environment.public_endpoint.rstrip('/')}/{environment.bucket}/{reference.key}"
        )
        with pytest.raises(HTTPError) as denied:
            urlopen(anonymous_url, timeout=10)
        assert denied.value.code in {401, 403}

        # SeaweedFS 3.85 ignores conditional-copy headers. A hostile replay can
        # mutate staging, but verification snapshots must keep canonical bytes
        # unchanged and a mismatched snapshot must never reach the final key.
        mismatched_upload_id = uuid7()
        mismatched = b"mutated staging bytes"
        client.put_object(
            Bucket=environment.staging_bucket,
            Key=f"organizations/{organization_id}/staging/{mismatched_upload_id}",
            Body=mismatched,
        )
        with pytest.raises(ObjectIntegrityError):
            adapter.snapshot_staging(
                organization_id=organization_id,
                upload_id=mismatched_upload_id,
                expected_sha256=digest,
                expected_byte_size=len(content),
            )
        assert (
            client.get_object(Bucket=reference.bucket, Key=reference.key)["Body"].read() == content
        )

        replay_upload_id = uuid7()
        replay_key = f"organizations/{organization_id}/staging/{replay_upload_id}"
        client.put_object(Bucket=environment.staging_bucket, Key=replay_key, Body=content)
        replay_snapshot = adapter.snapshot_staging(
            organization_id=organization_id,
            upload_id=replay_upload_id,
            expected_sha256=digest,
            expected_byte_size=len(content),
        )
        client.put_object(Bucket=environment.staging_bucket, Key=replay_key, Body=mismatched)
        promoter.promote_snapshot(replay_snapshot)
        adapter.cleanup_snapshot(replay_snapshot)
        assert (
            client.get_object(Bucket=reference.bucket, Key=reference.key)["Body"].read() == content
        )

        # The long-lived API credential may read permanent evidence but cannot
        # overwrite or delete it; permanent writes require an isolated boundary.
        with pytest.raises(ClientError) as denied_api_put:
            client.put_object(Bucket=reference.bucket, Key=reference.key, Body=b"tampered")
        assert denied_api_put.value.response["ResponseMetadata"]["HTTPStatusCode"] == 403
        with pytest.raises(ClientError) as denied_api_delete:
            client.delete_object(Bucket=reference.bucket, Key=reference.key)
        assert denied_api_delete.value.response["ResponseMetadata"]["HTTPStatusCode"] == 403
        assert (
            client.get_object(Bucket=reference.bucket, Key=reference.key)["Body"].read() == content
        )

        worker = boto3.client(
            "s3",
            endpoint_url=environment.endpoint,
            aws_access_key_id=environment.worker_access_key,
            aws_secret_access_key=environment.worker_secret_key,
            region_name="us-east-1",
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
        forbidden_key = f"organizations/{organization_id}/sha256/00/{'0' * 64}"
        with pytest.raises(ClientError) as denied_put:
            worker.put_object(Bucket=environment.bucket, Key=forbidden_key, Body=b"forbidden")
        assert denied_put.value.response["ResponseMetadata"]["HTTPStatusCode"] == 403
        with pytest.raises(ClientError) as denied_delete:
            worker.delete_object(Bucket=environment.bucket, Key=forbidden_key)
        assert denied_delete.value.response["ResponseMetadata"]["HTTPStatusCode"] == 403
        worker.delete_object(
            Bucket=environment.staging_bucket,
            Key=f"organizations/{organization_id}/staging/nonexistent-worker-probe",
        )

        adapter.cleanup_staging(
            StagingCleanupIntent(
                organization_id=organization_id,
                upload_id=upload_id,
            )
        )
        with pytest.raises(ClientError) as missing:
            client.head_object(
                Bucket=environment.staging_bucket,
                Key=f"organizations/{organization_id}/staging/{upload_id}",
            )
        assert missing.value.response["ResponseMetadata"]["HTTPStatusCode"] == 404
    finally:
        for bucket in (environment.bucket, environment.staging_bucket):
            response = admin.list_objects_v2(Bucket=bucket)
            objects = [{"Key": item["Key"]} for item in response.get("Contents", [])]
            if objects:
                admin.delete_objects(Bucket=bucket, Delete={"Objects": objects})
            admin.delete_bucket(Bucket=bucket)
