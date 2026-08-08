"""Opaque organization-isolated S3 key derivation."""

from __future__ import annotations

import hashlib
import hmac
from uuid import UUID

from pcbknowledge.platform.storage.errors import InvalidObjectDigestError


def require_sha256(value: str) -> str:
    """Accept only canonical lower-case SHA-256 hexadecimal."""

    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise InvalidObjectDigestError()
    return value


def content_addressed_key(organization_id: UUID, sha256: str) -> str:
    digest = require_sha256(sha256)
    return f"organizations/{organization_id}/sha256/{digest[:2]}/{digest}"


def staging_object_key(organization_id: UUID, upload_id: UUID) -> str:
    return f"organizations/{organization_id}/staging/{upload_id}"


def verification_object_key(organization_id: UUID, upload_id: UUID) -> str:
    """Return a backend-only mutable snapshot key for one reserved upload."""

    return f"organizations/{organization_id}/verification/{upload_id}"


def verify_bytes_sha256(content: bytes, expected_sha256: str) -> None:
    expected = require_sha256(expected_sha256)
    actual = hashlib.sha256(content).hexdigest()
    if not hmac.compare_digest(actual, expected):
        from pcbknowledge.platform.storage.errors import ObjectIntegrityError

        raise ObjectIntegrityError()
