"""Strict timezone-aware UTC handling for storage and API DTOs."""

import re
from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, BeforeValidator, PlainSerializer, WithJsonSchema

_RFC3339_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|z|[+-]\d{2}:\d{2})$"
)


class NaiveDateTimeError(ValueError):
    """Raised when a datetime has no usable timezone offset."""


def ensure_utc(value: datetime) -> datetime:
    """Reject naive datetimes and normalize aware values to UTC."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise NaiveDateTimeError("datetime must be timezone-aware")
    return value.astimezone(UTC)


def utc_now() -> datetime:
    """Return the current timezone-aware UTC instant."""

    return datetime.now(UTC)


def format_rfc3339(value: datetime) -> str:
    """Serialize an aware instant as canonical UTC RFC 3339."""

    normalized = ensure_utc(value)
    return normalized.isoformat(timespec="microseconds").replace("+00:00", "Z")


def parse_rfc3339(value: str) -> datetime:
    """Parse an RFC 3339 timestamp and normalize it to UTC."""

    if not _RFC3339_PATTERN.fullmatch(value):
        raise ValueError("timestamp must be an RFC 3339 date-time")
    candidate = value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError("timestamp must be an RFC 3339 date-time") from exc
    return ensure_utc(parsed)


def _parse_dto_value(value: object) -> object:
    return parse_rfc3339(value) if isinstance(value, str) else value


UTCDateTime = Annotated[
    datetime,
    BeforeValidator(_parse_dto_value),
    AfterValidator(ensure_utc),
    PlainSerializer(format_rfc3339, return_type=str, when_used="json"),
    WithJsonSchema({"type": "string", "format": "date-time"}, mode="serialization"),
]
"""Pydantic datetime annotation that rejects naive values and emits RFC 3339 UTC."""
