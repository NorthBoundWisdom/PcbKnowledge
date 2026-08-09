"""SeaweedFS S3 adapter with separated internal and browser signing endpoints."""

from __future__ import annotations

import hashlib
import hmac
import importlib
import re
import secrets
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol, cast
from urllib.parse import urlsplit
from urllib.request import Request as UrlRequest
from urllib.request import urlopen
from uuid import UUID

from pcbknowledge.platform.storage.errors import (
    ObjectDigestMismatchError,
    ObjectIntegrityError,
    ObjectMagicMismatchError,
    ObjectSizeMismatchError,
    ObjectStoreUnavailableError,
)
from pcbknowledge.platform.storage.keys import (
    content_addressed_key,
    require_sha256,
    staging_object_key,
    verification_object_key,
)

_BUCKET_NAME = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")


class StreamingBody(Protocol):
    def read(self, amount: int | None = None) -> bytes: ...

    def close(self) -> None: ...


class S3Client(Protocol):
    def head_bucket(self, **kwargs: object) -> Mapping[str, object]: ...

    def create_bucket(self, **kwargs: object) -> Mapping[str, object]: ...

    def generate_presigned_url(
        self,
        ClientMethod: str,
        Params: Mapping[str, object],
        ExpiresIn: int,
        HttpMethod: str | None = None,
    ) -> str: ...

    def get_object(self, **kwargs: object) -> Mapping[str, object]: ...

    def copy_object(self, **kwargs: object) -> object: ...

    def delete_object(self, **kwargs: object) -> object: ...

    def put_bucket_cors(self, **kwargs: object) -> object: ...

    def put_object(self, **kwargs: object) -> object: ...


@dataclass(frozen=True, slots=True)
class StoredObjectRef:
    bucket: str
    key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class PresignedRequest:
    url: str = field(repr=False)
    headers: Mapping[str, str]
    expires_in_seconds: int


@dataclass(frozen=True, slots=True)
class ObjectInspection:
    sha256: str
    byte_size: int
    entity_tag: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class StagingCleanupIntent:
    organization_id: UUID
    upload_id: UUID


@dataclass(frozen=True, slots=True)
class VerifiedStagingSnapshot:
    """Backend-only immutable snapshot verified before canonical promotion."""

    organization_id: UUID
    upload_id: UUID
    inspection: ObjectInspection
    key: str = field(repr=False)


class SeaweedFsS3Adapter:
    """S3-compatible storage operations used by intake and asset services."""

    def __init__(
        self,
        *,
        internal_client: S3Client,
        presign_client: S3Client,
        bucket: str,
        staging_bucket: str,
        max_upload_bytes: int = 268_435_456,
        allow_content_write: bool = False,
    ) -> None:
        if _BUCKET_NAME.fullmatch(bucket) is None:
            raise ValueError("invalid S3 bucket name")
        if _BUCKET_NAME.fullmatch(staging_bucket) is None or staging_bucket == bucket:
            raise ValueError("invalid or non-isolated staging bucket name")
        if not 1 <= max_upload_bytes <= 2_147_483_648:
            raise ValueError("invalid maximum upload size")
        self._internal = internal_client
        self._presign = presign_client
        self._bucket = bucket
        self._staging_bucket = staging_bucket
        self._max_upload_bytes = max_upload_bytes
        self._allow_content_write = allow_content_write

    @property
    def maximum_upload_bytes(self) -> int:
        """Return the configured qualified bound without exposing credentials."""

        return self._max_upload_bytes

    @classmethod
    def from_credentials(
        cls,
        *,
        internal_endpoint_url: str,
        public_endpoint_url: str,
        access_key_id: str,
        secret_access_key: str,
        bucket: str,
        staging_bucket: str,
        region_name: str = "us-east-1",
        max_upload_bytes: int = 268_435_456,
        allow_content_write: bool = False,
    ) -> SeaweedFsS3Adapter:
        """Create clients without retaining credential strings on the adapter."""

        boto3 = importlib.import_module("boto3")
        config_module = importlib.import_module("botocore.config")
        config_class = vars(config_module)["Config"]
        config = config_class(signature_version="s3v4", s3={"addressing_style": "path"})
        common = {
            "aws_access_key_id": access_key_id,
            "aws_secret_access_key": secret_access_key,
            "config": config,
            "region_name": region_name,
        }
        internal = cast(
            S3Client,
            boto3.client("s3", endpoint_url=internal_endpoint_url, **common),
        )
        presign = cast(
            S3Client,
            boto3.client("s3", endpoint_url=public_endpoint_url, **common),
        )
        return cls(
            internal_client=internal,
            presign_client=presign,
            bucket=bucket,
            staging_bucket=staging_bucket,
            max_upload_bytes=max_upload_bytes,
            allow_content_write=allow_content_write,
        )

    def presign_staging_put(
        self,
        *,
        organization_id: UUID,
        upload_id: UUID,
        media_type: str,
        expected_byte_size: int,
        expires_in_seconds: int = 900,
    ) -> PresignedRequest:
        self._validate_expiry(expires_in_seconds)
        self._validate_media_type(media_type)
        self._validate_expected_byte_size(expected_byte_size)
        try:
            url = self._presign.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": self._staging_bucket,
                    "Key": staging_object_key(organization_id, upload_id),
                    "ContentType": media_type,
                    "ContentLength": expected_byte_size,
                },
                ExpiresIn=expires_in_seconds,
                HttpMethod="PUT",
            )
        except Exception:
            raise ObjectStoreUnavailableError() from None
        if not isinstance(url, str) or not url:
            raise ObjectStoreUnavailableError() from None
        return PresignedRequest(
            url=url,
            headers={
                "Content-Type": media_type,
                "Content-Length": str(expected_byte_size),
            },
            expires_in_seconds=expires_in_seconds,
        )

    def probe_content_bucket(self) -> None:
        """Prove the permanent bucket is reachable with injected credentials."""

        try:
            self._internal.head_bucket(Bucket=self._bucket)
        except Exception:
            raise ObjectStoreUnavailableError() from None

    def probe_staging_bucket(self) -> None:
        """Prove the isolated staging bucket is reachable."""

        try:
            self._internal.head_bucket(Bucket=self._staging_bucket)
        except Exception:
            raise ObjectStoreUnavailableError() from None

    def probe_cleanup_access(self) -> None:
        """Prove worker delete access in a reserved, never-issued namespace."""

        try:
            self._internal.delete_object(
                Bucket=self._staging_bucket,
                Key=f"system/health/{secrets.token_hex(16)}",
            )
        except Exception:
            raise ObjectStoreUnavailableError() from None

    def probe_verifier_access(self) -> None:
        """Prove staging read/write/delete and permanent read without List/Admin."""

        staging_key = f"system/health/{secrets.token_hex(16)}"
        permanent_key = f"system/health/missing-{secrets.token_hex(16)}"
        try:
            self._internal.put_object(
                Bucket=self._staging_bucket,
                Key=staging_key,
                Body=b"pcbknowledge-verifier-health",
                ContentType="application/octet-stream",
            )
            inspection = self._inspect_key(self._staging_bucket, staging_key)
            if inspection.byte_size != len(b"pcbknowledge-verifier-health"):
                raise ObjectStoreUnavailableError()
            if self._inspect_key_if_exists(self._bucket, permanent_key) is not None:
                raise ObjectStoreUnavailableError()
        except ObjectStoreUnavailableError:
            raise
        except Exception:
            raise ObjectStoreUnavailableError() from None
        finally:
            try:
                self._internal.delete_object(Bucket=self._staging_bucket, Key=staging_key)
            except Exception:
                raise ObjectStoreUnavailableError() from None

    def probe_buckets(self) -> None:
        self.probe_content_bucket()
        self.probe_staging_bucket()

    def ensure_buckets(self) -> bool:
        """Create the configured buckets if absent and verify before returning.

        This method belongs to an explicit deployment initializer. Request paths
        and readiness probes never create infrastructure as a side effect.
        """

        created = False
        for bucket in (self._bucket, self._staging_bucket):
            created = self._ensure_bucket(bucket) or created
        return created

    def configure_staging_cors(self, *, allowed_origins: Sequence[str]) -> None:
        """Install or qualify an externally managed exact browser-origin gate."""

        origins = tuple(dict.fromkeys(allowed_origins))
        if not 1 <= len(origins) <= 32:
            raise ValueError("at least one bounded staging CORS origin is required")
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                "*" in origin
                or parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("staging CORS origins must be exact HTTP origins")
        try:
            self._internal.put_bucket_cors(
                Bucket=self._staging_bucket,
                CORSConfiguration={
                    "CORSRules": [
                        {
                            "AllowedOrigins": list(origins),
                            "AllowedMethods": ["PUT"],
                            "AllowedHeaders": ["Content-Type"],
                            "ExposeHeaders": ["ETag"],
                            "MaxAgeSeconds": 600,
                        }
                    ]
                },
            )
        except Exception as error:
            if not self._is_not_implemented(error):
                raise ObjectStoreUnavailableError() from None
            self._qualify_external_staging_cors(origins)

    def _qualify_external_staging_cors(self, origins: tuple[str, ...]) -> None:
        """Qualify SeaweedFS 3.85's exact process-level CORS configuration."""

        try:
            # This deployment-only probe runs inside the Compose network. The
            # browser signer points at host loopback, which is intentionally
            # unreachable here, so qualify via the authenticated internal
            # endpoint while exercising the same bucket and object contract.
            url = self._internal.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": self._staging_bucket,
                    "Key": f"system/cors/{secrets.token_hex(16)}",
                    "ContentType": "application/pdf",
                    "ContentLength": 1,
                },
                ExpiresIn=60,
                HttpMethod="PUT",
            )
            if not isinstance(url, str) or not url:
                raise ObjectStoreUnavailableError()
            for origin in origins:
                request = UrlRequest(
                    url,
                    method="OPTIONS",
                    headers={
                        "Origin": origin,
                        "Access-Control-Request-Method": "PUT",
                        "Access-Control-Request-Headers": "content-type",
                    },
                )
                with urlopen(request, timeout=10) as response:
                    allowed_origin = response.headers.get("Access-Control-Allow-Origin")
                    allowed_methods = response.headers.get("Access-Control-Allow-Methods", "")
                    allowed_headers = response.headers.get("Access-Control-Allow-Headers", "")
                    if (
                        response.status not in {200, 204}
                        or allowed_origin not in {origin, "*"}
                        or not ("PUT" in allowed_methods.upper() or allowed_methods.strip() == "*")
                        or not (
                            "content-type" in allowed_headers.casefold()
                            or allowed_headers.strip() == "*"
                        )
                    ):
                        raise ObjectStoreUnavailableError()

        except ObjectStoreUnavailableError:
            raise
        except Exception:
            raise ObjectStoreUnavailableError() from None

    def _ensure_bucket(self, bucket: str) -> bool:

        try:
            self._internal.head_bucket(Bucket=bucket)
            return False
        except Exception:
            pass

        try:
            self._internal.create_bucket(Bucket=bucket)
        except Exception:
            # A concurrent initializer or a lost response can leave the bucket
            # present. A final authenticated probe is the only safe arbiter.
            try:
                self._internal.head_bucket(Bucket=bucket)
            except Exception:
                raise ObjectStoreUnavailableError() from None
            return False

        try:
            self._internal.head_bucket(Bucket=bucket)
        except Exception:
            raise ObjectStoreUnavailableError() from None
        return True

    def snapshot_staging(
        self,
        *,
        organization_id: UUID,
        upload_id: UUID,
        expected_sha256: str | None = None,
        expected_byte_size: int | None = None,
        required_prefix: bytes | None = None,
    ) -> VerifiedStagingSnapshot:
        expected = require_sha256(expected_sha256) if expected_sha256 is not None else None
        if required_prefix is not None and not 1 <= len(required_prefix) <= 64:
            raise ValueError("required object prefix is invalid")
        source_key = staging_object_key(organization_id, upload_id)
        snapshot_key = verification_object_key(organization_id, upload_id)
        try:
            self._internal.copy_object(
                Bucket=self._staging_bucket,
                Key=snapshot_key,
                CopySource={"Bucket": self._staging_bucket, "Key": source_key},
                MetadataDirective="COPY",
            )
            inspection = self._inspect_key(
                self._staging_bucket,
                snapshot_key,
                required_prefix=required_prefix,
            )
            if expected_byte_size is not None and inspection.byte_size != expected_byte_size:
                raise ObjectSizeMismatchError()
            if expected is not None and not hmac.compare_digest(inspection.sha256, expected):
                raise ObjectDigestMismatchError()
        except ObjectIntegrityError, ObjectStoreUnavailableError:
            self._discard_failed_snapshot(snapshot_key)
            raise
        except Exception:
            self._discard_failed_snapshot(snapshot_key)
            raise ObjectStoreUnavailableError() from None
        return VerifiedStagingSnapshot(
            organization_id=organization_id,
            upload_id=upload_id,
            inspection=inspection,
            key=snapshot_key,
        )

    def _discard_failed_snapshot(self, snapshot_key: str) -> None:
        try:
            self._internal.delete_object(Bucket=self._staging_bucket, Key=snapshot_key)
        except Exception:
            raise ObjectStoreUnavailableError() from None

    def promote_snapshot(self, snapshot: VerifiedStagingSnapshot) -> StoredObjectRef:
        """Promote under the caller's PostgreSQL content lock without overwrite.

        SeaweedFS 3.85 does not enforce S3 conditional-copy headers. Therefore
        this boundary first verifies a backend-only snapshot, and it never sends
        CopyObject when the canonical key already exists.
        """

        if not self._allow_content_write:
            # The long-lived API and cleanup worker credentials deliberately
            # cannot mutate permanent evidence. M2 promotion is performed only
            # by an explicitly privileged, isolated verifier boundary.
            raise ObjectStoreUnavailableError()

        destination_key = content_addressed_key(
            snapshot.organization_id,
            snapshot.inspection.sha256,
        )
        existing = self._inspect_key_if_exists(self._bucket, destination_key)
        if existing is not None:
            self._require_same_content(snapshot.inspection, existing)
            return StoredObjectRef(self._bucket, destination_key)
        try:
            self._internal.copy_object(
                Bucket=self._bucket,
                Key=destination_key,
                CopySource={"Bucket": self._staging_bucket, "Key": snapshot.key},
                MetadataDirective="COPY",
            )
        except Exception:
            raise ObjectStoreUnavailableError() from None
        final_inspection = self._inspect_key(self._bucket, destination_key)
        self._require_same_content(snapshot.inspection, final_inspection)
        return StoredObjectRef(self._bucket, destination_key)

    def cleanup_snapshot(self, snapshot: VerifiedStagingSnapshot) -> None:
        try:
            self._internal.delete_object(Bucket=self._staging_bucket, Key=snapshot.key)
        except Exception:
            raise ObjectStoreUnavailableError() from None

    def cleanup_staging(self, intent: StagingCleanupIntent) -> None:
        """Delete staging only from an outbox consumer after registry commit."""

        try:
            self._internal.delete_object(
                Bucket=self._staging_bucket,
                Key=staging_object_key(intent.organization_id, intent.upload_id),
            )
            self._internal.delete_object(
                Bucket=self._staging_bucket,
                Key=verification_object_key(intent.organization_id, intent.upload_id),
            )
        except Exception:
            raise ObjectStoreUnavailableError() from None

    def inspect_content(self, *, organization_id: UUID, sha256: str) -> ObjectInspection:
        return self._inspect_key(
            self._bucket,
            content_addressed_key(organization_id, sha256),
        )

    def presign_download(
        self, reference: StoredObjectRef, *, expires_in_seconds: int = 300
    ) -> PresignedRequest:
        self._validate_expiry(expires_in_seconds)
        if reference.bucket != self._bucket:
            raise ObjectStoreUnavailableError()
        try:
            url = self._presign.generate_presigned_url(
                "get_object",
                Params={"Bucket": reference.bucket, "Key": reference.key},
                ExpiresIn=expires_in_seconds,
                HttpMethod="GET",
            )
        except Exception:
            raise ObjectStoreUnavailableError() from None
        if not isinstance(url, str) or not url:
            raise ObjectStoreUnavailableError()
        return PresignedRequest(url=url, headers={}, expires_in_seconds=expires_in_seconds)

    def _inspect_key(
        self,
        bucket: str,
        key: str,
        *,
        required_prefix: bytes | None = None,
    ) -> ObjectInspection:
        inspection = self._inspect_key_or_none(
            bucket,
            key,
            required_prefix=required_prefix,
        )
        if inspection is None:
            raise ObjectStoreUnavailableError()
        return inspection

    def _inspect_key_if_exists(self, bucket: str, key: str) -> ObjectInspection | None:
        return self._inspect_key_or_none(bucket, key)

    def _inspect_key_or_none(
        self,
        bucket: str,
        key: str,
        *,
        required_prefix: bytes | None = None,
    ) -> ObjectInspection | None:
        try:
            response = self._internal.get_object(Bucket=bucket, Key=key)
            raw_body = response.get("Body")
            entity_tag = response.get("ETag")
            if raw_body is None or not isinstance(entity_tag, str) or not entity_tag:
                raise ObjectStoreUnavailableError()
            body = cast(StreamingBody, raw_body)
            digest = hashlib.sha256()
            byte_size = 0
            prefix = bytearray()
            try:
                while chunk := body.read(1024 * 1024):
                    if required_prefix is not None and len(prefix) < len(required_prefix):
                        missing = len(required_prefix) - len(prefix)
                        prefix.extend(chunk[:missing])
                    digest.update(chunk)
                    byte_size += len(chunk)
                    if byte_size > self._max_upload_bytes:
                        raise ObjectIntegrityError()
            finally:
                body.close()
            if required_prefix is not None and not hmac.compare_digest(
                bytes(prefix), required_prefix
            ):
                raise ObjectMagicMismatchError()
            return ObjectInspection(
                sha256=digest.hexdigest(),
                byte_size=byte_size,
                entity_tag=entity_tag,
            )
        except ObjectIntegrityError, ObjectStoreUnavailableError:
            raise
        except Exception as error:
            if self._is_missing_object(error):
                return None
            raise ObjectStoreUnavailableError() from None

    @staticmethod
    def _is_missing_object(error: Exception) -> bool:
        if isinstance(error, KeyError):
            return True
        response = getattr(error, "response", None)
        if not isinstance(response, Mapping):
            return False
        details = response.get("Error")
        code = details.get("Code") if isinstance(details, Mapping) else None
        metadata = response.get("ResponseMetadata")
        status = metadata.get("HTTPStatusCode") if isinstance(metadata, Mapping) else None
        return code in {"404", "NoSuchKey", "NotFound"} or status == 404

    @staticmethod
    def _is_not_implemented(error: Exception) -> bool:
        response = getattr(error, "response", None)
        if not isinstance(response, Mapping):
            return False
        details = response.get("Error")
        code = details.get("Code") if isinstance(details, Mapping) else None
        metadata = response.get("ResponseMetadata")
        status = metadata.get("HTTPStatusCode") if isinstance(metadata, Mapping) else None
        return code in {"501", "NotImplemented"} or status == 501

    @staticmethod
    def _validate_expiry(value: int) -> None:
        if not 1 <= value <= 3600:
            raise ValueError("presigned URL expiry must be between 1 and 3600 seconds")

    @staticmethod
    def _require_same_content(
        source: ObjectInspection,
        destination: ObjectInspection,
    ) -> None:
        if source.byte_size != destination.byte_size or not hmac.compare_digest(
            source.sha256, destination.sha256
        ):
            raise ObjectIntegrityError()

    @staticmethod
    def _validate_media_type(value: str) -> None:
        if not value or len(value) > 200 or "\r" in value or "\n" in value:
            raise ValueError("media type is invalid")

    def _validate_expected_byte_size(self, value: int) -> None:
        if not 1 <= value <= self._max_upload_bytes:
            raise ValueError("object size is outside the configured upload bound")
