"""Unit tests for opaque keys, integrity, and deferred staging cleanup."""

import hashlib
from collections.abc import Mapping
from typing import cast
from uuid import uuid7

import pytest

from pcbknowledge.platform.storage import (
    InvalidObjectDigestError,
    ObjectIntegrityError,
    ObjectStoreUnavailableError,
    SeaweedFsS3Adapter,
    content_addressed_key,
    staging_object_key,
    verify_bytes_sha256,
)
from pcbknowledge.platform.storage.adapter import S3Client, StagingCleanupIntent


class _Body:
    def __init__(self, content: bytes) -> None:
        self._content = content
        self._offset = 0

    def read(self, amount: int | None = None) -> bytes:
        if amount is None:
            amount = len(self._content)
        start = self._offset
        self._offset += amount
        return self._content[start : self._offset]

    def close(self) -> None:
        return None


class _FakeS3:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.deleted: list[str] = []
        self.buckets: set[str] = set()
        self.copies: list[tuple[str, str, str, str]] = []

    def head_bucket(self, **kwargs: object) -> Mapping[str, object]:
        bucket = cast(str, kwargs["Bucket"])
        if bucket not in self.buckets:
            raise RuntimeError("missing bucket")
        return {}

    def create_bucket(self, **kwargs: object) -> Mapping[str, object]:
        self.buckets.add(cast(str, kwargs["Bucket"]))
        return {}

    def generate_presigned_url(
        self,
        ClientMethod: str,
        Params: Mapping[str, object],
        ExpiresIn: int,
        HttpMethod: str | None = None,
    ) -> str:
        del ExpiresIn, HttpMethod
        return f"https://objects.invalid/{ClientMethod}/{Params['Bucket']}"

    def get_object(self, **kwargs: object) -> Mapping[str, object]:
        key = cast(str, kwargs["Key"])
        content = self.objects[key]
        return {
            "Body": _Body(content),
            "ETag": hashlib.sha256(content).hexdigest(),
        }

    def copy_object(self, **kwargs: object) -> object:
        key = cast(str, kwargs["Key"])
        source = cast(dict[str, str], kwargs["CopySource"])
        source_content = self.objects[source["Key"]]
        self.copies.append(
            (
                source["Bucket"],
                source["Key"],
                cast(str, kwargs["Bucket"]),
                key,
            )
        )
        self.objects[key] = source_content
        return {}

    def delete_object(self, **kwargs: object) -> object:
        key = cast(str, kwargs["Key"])
        self.deleted.append(key)
        self.objects.pop(key, None)
        return {}


class _NonCompliantMutatingS3(_FakeS3):
    """Simulate a backend that ignores both CopyObject preconditions."""

    def copy_object(self, **kwargs: object) -> object:
        source = cast(dict[str, str], kwargs["CopySource"])
        self.objects[source["Key"]] = b"mutated-after-inspection"
        return super().copy_object(**kwargs)


def test_content_keys_are_strict_and_organization_isolated() -> None:
    first_org = uuid7()
    second_org = uuid7()
    digest = hashlib.sha256(b"evidence").hexdigest()

    first = content_addressed_key(first_org, digest)
    second = content_addressed_key(second_org, digest)
    assert str(first_org) in first
    assert first != second
    assert repr(first).find(digest) >= 0
    with pytest.raises(InvalidObjectDigestError):
        content_addressed_key(first_org, digest.upper())
    with pytest.raises(ObjectIntegrityError):
        verify_bytes_sha256(b"different", digest)


def test_promotion_keeps_staging_until_explicit_outbox_cleanup() -> None:
    organization_id = uuid7()
    upload_id = uuid7()
    content = b"immutable evidence bytes"
    digest = hashlib.sha256(content).hexdigest()
    fake = _FakeS3()
    source_key = staging_object_key(organization_id, upload_id)
    fake.objects[source_key] = content
    adapter = SeaweedFsS3Adapter(
        internal_client=cast(S3Client, fake),
        presign_client=cast(S3Client, fake),
        bucket="pcbknowledge-test",
        staging_bucket="pcbknowledge-test-staging",
        allow_content_write=True,
    )

    snapshot = adapter.snapshot_staging(
        organization_id=organization_id,
        upload_id=upload_id,
        expected_sha256=digest,
        expected_byte_size=len(content),
    )
    reference = adapter.promote_snapshot(snapshot)
    inspection = snapshot.inspection

    assert inspection.byte_size == len(content)
    assert reference.key == content_addressed_key(organization_id, digest)
    assert source_key in fake.objects
    assert fake.deleted == []

    adapter.cleanup_snapshot(snapshot)
    adapter.cleanup_staging(
        StagingCleanupIntent(organization_id=organization_id, upload_id=upload_id)
    )
    assert source_key not in fake.objects
    assert source_key in fake.deleted


def test_missing_staging_cannot_alias_an_existing_org_content_digest() -> None:
    organization_id = uuid7()
    upload_id = uuid7()
    content = b"another project's protected evidence"
    digest = hashlib.sha256(content).hexdigest()
    fake = _FakeS3()
    fake.objects[content_addressed_key(organization_id, digest)] = content
    adapter = SeaweedFsS3Adapter(
        internal_client=cast(S3Client, fake),
        presign_client=cast(S3Client, fake),
        bucket="pcbknowledge-test",
        staging_bucket="pcbknowledge-test-staging",
    )

    with pytest.raises(ObjectStoreUnavailableError):
        adapter.snapshot_staging(
            organization_id=organization_id,
            upload_id=upload_id,
            expected_sha256=digest,
            expected_byte_size=len(content),
        )


def test_promotion_detects_a_backend_that_ignores_copy_preconditions() -> None:
    organization_id = uuid7()
    upload_id = uuid7()
    content = b"verified-before-copy"
    digest = hashlib.sha256(content).hexdigest()
    fake = _NonCompliantMutatingS3()
    fake.objects[staging_object_key(organization_id, upload_id)] = content
    adapter = SeaweedFsS3Adapter(
        internal_client=cast(S3Client, fake),
        presign_client=cast(S3Client, fake),
        bucket="pcbknowledge-test",
        staging_bucket="pcbknowledge-test-staging",
    )

    with pytest.raises(ObjectIntegrityError):
        adapter.snapshot_staging(
            organization_id=organization_id,
            upload_id=upload_id,
            expected_sha256=digest,
            expected_byte_size=len(content),
        )


def test_existing_content_addressed_object_is_never_overwritten() -> None:
    organization_id = uuid7()
    upload_id = uuid7()
    content = b"same immutable content"
    digest = hashlib.sha256(content).hexdigest()
    source_key = staging_object_key(organization_id, upload_id)
    destination_key = content_addressed_key(organization_id, digest)
    fake = _FakeS3()
    fake.objects[source_key] = content
    fake.objects[destination_key] = content
    adapter = SeaweedFsS3Adapter(
        internal_client=cast(S3Client, fake),
        presign_client=cast(S3Client, fake),
        bucket="pcbknowledge-test",
        staging_bucket="pcbknowledge-test-staging",
        allow_content_write=True,
    )

    snapshot = adapter.snapshot_staging(
        organization_id=organization_id,
        upload_id=upload_id,
        expected_sha256=digest,
        expected_byte_size=len(content),
    )
    adapter.promote_snapshot(snapshot)

    assert fake.objects[destination_key] == content
    assert [copy for copy in fake.copies if copy[3] == destination_key] == []


def test_default_runtime_adapter_cannot_write_permanent_content() -> None:
    organization_id = uuid7()
    upload_id = uuid7()
    content = b"verified but not privileged for permanent promotion"
    digest = hashlib.sha256(content).hexdigest()
    fake = _FakeS3()
    fake.objects[staging_object_key(organization_id, upload_id)] = content
    adapter = SeaweedFsS3Adapter(
        internal_client=cast(S3Client, fake),
        presign_client=cast(S3Client, fake),
        bucket="pcbknowledge-test",
        staging_bucket="pcbknowledge-test-staging",
    )

    snapshot = adapter.snapshot_staging(
        organization_id=organization_id,
        upload_id=upload_id,
        expected_sha256=digest,
        expected_byte_size=len(content),
    )
    with pytest.raises(ObjectStoreUnavailableError):
        adapter.promote_snapshot(snapshot)
    assert content_addressed_key(organization_id, digest) not in fake.objects


def test_presigned_values_hide_urls_and_object_keys_from_repr() -> None:
    organization_id = uuid7()
    upload_id = uuid7()
    fake = _FakeS3()
    adapter = SeaweedFsS3Adapter(
        internal_client=cast(S3Client, fake),
        presign_client=cast(S3Client, fake),
        bucket="pcbknowledge-test",
        staging_bucket="pcbknowledge-test-staging",
    )

    request = adapter.presign_staging_put(
        organization_id=organization_id,
        upload_id=upload_id,
        media_type="application/pdf",
        expected_byte_size=123,
    )

    assert request.url not in repr(request)
    assert "organizations/" not in repr(request)
    assert request.headers["Content-Length"] == "123"


def test_bucket_initialization_is_explicit_and_idempotent() -> None:
    fake = _FakeS3()
    adapter = SeaweedFsS3Adapter(
        internal_client=cast(S3Client, fake),
        presign_client=cast(S3Client, fake),
        bucket="pcbknowledge-test",
        staging_bucket="pcbknowledge-test-staging",
    )

    with pytest.raises(ObjectStoreUnavailableError):
        adapter.probe_buckets()
    assert adapter.ensure_buckets() is True
    adapter.probe_buckets()
    assert adapter.ensure_buckets() is False


def test_upload_size_is_bounded_before_signing_and_while_streaming() -> None:
    organization_id = uuid7()
    upload_id = uuid7()
    oversized = b"12345"
    fake = _FakeS3()
    fake.objects[staging_object_key(organization_id, upload_id)] = oversized
    adapter = SeaweedFsS3Adapter(
        internal_client=cast(S3Client, fake),
        presign_client=cast(S3Client, fake),
        bucket="pcbknowledge-test",
        staging_bucket="pcbknowledge-test-staging",
        max_upload_bytes=4,
    )

    with pytest.raises(ValueError, match="upload bound"):
        adapter.presign_staging_put(
            organization_id=organization_id,
            upload_id=upload_id,
            media_type="application/pdf",
            expected_byte_size=len(oversized),
        )
    with pytest.raises(ObjectIntegrityError):
        adapter.snapshot_staging(
            organization_id=organization_id,
            upload_id=upload_id,
            expected_sha256=hashlib.sha256(oversized).hexdigest(),
        )
