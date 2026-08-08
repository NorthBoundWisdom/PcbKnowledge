"""Credential-safe authentication failures."""

from enum import StrEnum


class AuthenticationFailure(StrEnum):
    """Stable failure categories safe for metrics and problem responses."""

    MALFORMED_TOKEN = "MALFORMED_TOKEN"
    DISALLOWED_ALGORITHM = "DISALLOWED_ALGORITHM"
    SIGNING_KEY_UNAVAILABLE = "SIGNING_KEY_UNAVAILABLE"
    INVALID_TOKEN = "INVALID_TOKEN"
    INVALID_CLAIMS = "INVALID_CLAIMS"
    CLIENT_KIND_MISMATCH = "CLIENT_KIND_MISMATCH"
    SUBJECT_NOT_MAPPED = "SUBJECT_NOT_MAPPED"
    SUBJECT_DISABLED = "SUBJECT_DISABLED"
    SUBJECT_MAPPING_MISMATCH = "SUBJECT_MAPPING_MISMATCH"
    MEMBERSHIP_MISSING = "MEMBERSHIP_MISSING"


class AuthenticationError(Exception):
    """Fail-closed authentication error without raw token or key details."""

    def __init__(self, reason: AuthenticationFailure) -> None:
        super().__init__("authentication failed")
        self.reason = reason


class SigningKeyResolutionError(Exception):
    """A configured resolver could not produce the requested trusted key."""


class MalformedSigningTokenError(SigningKeyResolutionError):
    """The resolver rejected token structure before consulting trust keys."""
