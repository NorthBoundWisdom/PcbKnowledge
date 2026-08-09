"""Authorized content-addressed object storage public surface."""

from pcbknowledge.platform.storage.adapter import (
    ObjectInspection,
    PresignedRequest,
    SeaweedFsS3Adapter,
    StoredObjectRef,
    VerifiedStagingSnapshot,
)
from pcbknowledge.platform.storage.audit import AuditWriterAssetReadAuditor
from pcbknowledge.platform.storage.authorization import PolicyStorageAuthorizer
from pcbknowledge.platform.storage.errors import (
    InvalidObjectDigestError,
    ObjectAccessDeniedError,
    ObjectAssetNotFoundError,
    ObjectAuditRequiredError,
    ObjectDigestMismatchError,
    ObjectIntegrityError,
    ObjectMagicMismatchError,
    ObjectSizeMismatchError,
    ObjectStoreUnavailableError,
    StagingUploadNotFoundError,
    StagingUploadStateError,
    StorageError,
)
from pcbknowledge.platform.storage.keys import (
    content_addressed_key,
    require_sha256,
    staging_object_key,
    verification_object_key,
    verify_bytes_sha256,
)
from pcbknowledge.platform.storage.models import (
    ObjectAsset,
    ObjectAssetState,
    StagingUploadReservation,
    StagingUploadState,
)
from pcbknowledge.platform.storage.repository import (
    ObjectAssetRepository,
    StagingUploadRepository,
)
from pcbknowledge.platform.storage.runtime import (
    build_object_storage_adapter,
    get_object_storage_adapter,
    initialize_object_storage,
    probe_object_storage,
    reset_object_storage_adapter,
)
from pcbknowledge.platform.storage.service import (
    AssetDownload,
    AssetReadAuditor,
    ObjectStorageService,
    StagingUpload,
    StorageAuthorizer,
    StorageRequestContext,
)

__all__ = [
    "AssetDownload",
    "AssetReadAuditor",
    "AuditWriterAssetReadAuditor",
    "InvalidObjectDigestError",
    "ObjectAccessDeniedError",
    "ObjectAsset",
    "ObjectAssetNotFoundError",
    "ObjectAssetRepository",
    "ObjectAssetState",
    "ObjectAuditRequiredError",
    "ObjectDigestMismatchError",
    "ObjectInspection",
    "ObjectIntegrityError",
    "ObjectMagicMismatchError",
    "ObjectSizeMismatchError",
    "ObjectStorageService",
    "ObjectStoreUnavailableError",
    "PolicyStorageAuthorizer",
    "PresignedRequest",
    "SeaweedFsS3Adapter",
    "StagingUpload",
    "StagingUploadNotFoundError",
    "StagingUploadRepository",
    "StagingUploadReservation",
    "StagingUploadState",
    "StagingUploadStateError",
    "StorageAuthorizer",
    "StorageError",
    "StorageRequestContext",
    "StoredObjectRef",
    "VerifiedStagingSnapshot",
    "build_object_storage_adapter",
    "content_addressed_key",
    "get_object_storage_adapter",
    "initialize_object_storage",
    "probe_object_storage",
    "require_sha256",
    "reset_object_storage_adapter",
    "staging_object_key",
    "verification_object_key",
    "verify_bytes_sha256",
]
