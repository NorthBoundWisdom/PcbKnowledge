"""Bounded JSON metadata validation shared by durable platform queues."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from collections.abc import Mapping
from typing import cast

from pcbknowledge.platform.jobs.errors import InvalidJobPayloadError

type JsonScalar = str | int | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]

MAX_PAYLOAD_BYTES = 8 * 1024
MAX_CONTAINER_ITEMS = 64
MAX_DEPTH = 5
MAX_STRING_LENGTH = 512

_SENSITIVE_KEY_PARTS = frozenset(
    {
        "authorization",
        "bytes",
        "content",
        "cookie",
        "credential",
        "password",
        "raw",
        "secret",
        "token",
    }
)


def _canonical_key(value: str) -> str:
    camel_separated = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", value)
    return re.sub(r"[^a-z0-9]+", "_", camel_separated.casefold()).strip("_")


def _reject_sensitive_key(value: str) -> None:
    normalized = _canonical_key(value)
    parts = frozenset(normalized.split("_"))
    if (
        parts.intersection(_SENSITIVE_KEY_PARTS)
        or {"source", "text"} <= parts
        or {"full", "text"} <= parts
        or {"model", "input"} <= parts
        or {"model", "output"} <= parts
    ):
        raise InvalidJobPayloadError()


def validate_small_metadata(payload: Mapping[str, object]) -> tuple[dict[str, JsonValue], str]:
    """Validate and canonicalize a small identifier/metadata payload.

    Payloads are intentionally bounded so a queue row never becomes storage for
    document text, source bytes, credentials, or model input/output.
    """

    normalized = dict(payload)
    _validate_value(normalized, depth=0)
    try:
        canonical = json.dumps(
            normalized,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    except (TypeError, ValueError) as exc:
        raise InvalidJobPayloadError() from exc
    if len(canonical) > MAX_PAYLOAD_BYTES:
        raise InvalidJobPayloadError()
    return cast(dict[str, JsonValue], normalized), hashlib.sha256(canonical).hexdigest()


def payload_digest_matches(payload: Mapping[str, object], expected_sha256: str) -> bool:
    """Revalidate untrusted persisted metadata and compare its canonical digest."""

    try:
        validate_sha256(expected_sha256)
        _normalized, actual_sha256 = validate_small_metadata(payload)
    except InvalidJobPayloadError:
        return False
    return hmac.compare_digest(actual_sha256, expected_sha256)


def validate_sha256(value: str) -> str:
    """Require a lowercase hexadecimal SHA-256 digest."""

    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise InvalidJobPayloadError()
    return value


def _validate_value(value: object, *, depth: int) -> None:
    if depth > MAX_DEPTH:
        raise InvalidJobPayloadError()
    if value is None or isinstance(value, bool | int):
        return
    if isinstance(value, float):
        # PostgreSQL JSONB normalizes numeric spellings differently from
        # Python's JSON encoder (notably exponent notation and negative zero).
        # Queue metadata needs a cross-runtime stable digest, so M1 accepts
        # bounded integers only.
        raise InvalidJobPayloadError()
    if isinstance(value, str):
        if len(value) > MAX_STRING_LENGTH:
            raise InvalidJobPayloadError()
        return
    if isinstance(value, dict):
        if len(value) > MAX_CONTAINER_ITEMS:
            raise InvalidJobPayloadError()
        for key, nested in value.items():
            if not isinstance(key, str) or not key or len(key) > 128:
                raise InvalidJobPayloadError()
            _reject_sensitive_key(key)
            _validate_value(nested, depth=depth + 1)
        return
    if isinstance(value, list):
        if len(value) > MAX_CONTAINER_ITEMS:
            raise InvalidJobPayloadError()
        for nested in value:
            _validate_value(nested, depth=depth + 1)
        return
    raise InvalidJobPayloadError()
