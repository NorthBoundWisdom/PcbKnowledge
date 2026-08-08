"""Canonical UUIDv7 primitives for public and persistent identifiers."""

import uuid
from typing import Annotated

from pydantic import AfterValidator


class InvalidUUID7Error(ValueError):
    """Raised when a value is not an RFC 9562 UUIDv7 identifier."""


def is_uuid7(value: object) -> bool:
    """Return whether ``value`` is an RFC 4122-variant UUIDv7."""

    return isinstance(value, uuid.UUID) and value.version == 7 and value.variant == uuid.RFC_4122


def require_uuid7(value: uuid.UUID) -> uuid.UUID:
    """Validate and return a UUIDv7 value for Pydantic and domain boundaries."""

    if not is_uuid7(value):
        raise InvalidUUID7Error("identifier must be an RFC 9562 UUIDv7")
    return value


def new_uuid7() -> uuid.UUID:
    """Generate a time-ordered UUIDv7 using the Python 3.14 standard library."""

    value = uuid.uuid7()
    return require_uuid7(value)


UUID7 = Annotated[uuid.UUID, AfterValidator(require_uuid7)]
"""Pydantic-compatible UUIDv7 annotation."""
