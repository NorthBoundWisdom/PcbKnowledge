"""Process-scoped object-storage adapter and deployment probes."""

from functools import lru_cache

from pcbknowledge.platform.config import ObjectStorageSettings, get_object_storage_settings
from pcbknowledge.platform.storage.adapter import SeaweedFsS3Adapter


def build_object_storage_adapter(settings: ObjectStorageSettings) -> SeaweedFsS3Adapter:
    """Build the S3 boundary without exposing credentials through repr or logs."""

    return SeaweedFsS3Adapter.from_credentials(
        internal_endpoint_url=str(settings.endpoint_url).rstrip("/"),
        public_endpoint_url=str(settings.public_endpoint_url).rstrip("/"),
        access_key_id=settings.access_key.get_secret_value(),
        secret_access_key=settings.secret_key.get_secret_value(),
        bucket=settings.bucket,
        staging_bucket=settings.staging_bucket,
        region_name=settings.region,
        max_upload_bytes=settings.max_upload_bytes,
        allow_content_write=settings.access_mode == "admin",
    )


@lru_cache(maxsize=1)
def get_object_storage_adapter() -> SeaweedFsS3Adapter:
    """Return one credentials-backed adapter per process."""

    return build_object_storage_adapter(get_object_storage_settings())


def probe_object_storage(settings: ObjectStorageSettings) -> None:
    """Execute an authenticated bucket probe without creating infrastructure."""

    adapter = build_object_storage_adapter(settings)
    if settings.access_mode == "worker":
        adapter.probe_cleanup_access()
    else:
        adapter.probe_buckets()


def initialize_object_storage(settings: ObjectStorageSettings) -> bool:
    """Idempotently create the configured bucket from an explicit tool command."""

    if settings.access_mode != "admin":
        raise ValueError("object storage initialization requires admin access mode")
    return build_object_storage_adapter(settings).ensure_buckets()


def reset_object_storage_adapter() -> None:
    """Clear the cached adapter for isolated tests or credential rotation."""

    get_object_storage_adapter.cache_clear()
