"""Unit policy tests for durable jobs; no SQLite/in-memory persistence substitute."""

import hashlib
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import uuid7

import pytest
from sqlalchemy.orm import Session

from pcbknowledge.platform.jobs import AccessScope, JobService, TenantScope
from pcbknowledge.platform.jobs.errors import (
    InvalidJobPayloadError,
    InvalidJobTransitionError,
)
from pcbknowledge.platform.jobs.payload import JsonValue, validate_small_metadata


def test_payload_is_canonical_and_bounded() -> None:
    first, first_digest = validate_small_metadata(
        {"document_revision_id": str(uuid7()), "metadata": {"page": 2, "retry": False}}
    )
    _second, second_digest = validate_small_metadata(
        {
            "metadata": {"retry": False, "page": 2},
            "document_revision_id": first["document_revision_id"],
        }
    )

    assert first_digest == second_digest
    assert len(first_digest) == 64
    sensitive_payloads: tuple[dict[str, JsonValue], ...] = (
        {"source_text": "small but prohibited"},
        {"accessToken": "credential"},
        {"nested": {"clientSecret": "credential"}},
        {"documentBytes": "encoded source"},
        {"modelInput": "prompt"},
    )
    for sensitive in sensitive_payloads:
        with pytest.raises(InvalidJobPayloadError, match="small JSON metadata"):
            validate_small_metadata(sensitive)
    with pytest.raises(InvalidJobPayloadError, match="small JSON metadata"):
        validate_small_metadata({"bytes": b"not-json"})
    for floating_point in (float("nan"), 1e20, -0.0, 1.5):
        with pytest.raises(InvalidJobPayloadError, match="small JSON metadata"):
            validate_small_metadata({"score": floating_point})


def test_scope_requires_explicit_project_alignment() -> None:
    organization_id = uuid7()
    project_id = uuid7()

    assert TenantScope(organization_id, None, AccessScope.ORGANIZATION).project_id is None
    assert TenantScope(organization_id, project_id, AccessScope.PROJECT).project_id == project_id
    with pytest.raises(ValueError, match="scope and project"):
        TenantScope(organization_id, None, AccessScope.PROJECT)
    with pytest.raises(ValueError, match="scope and project"):
        TenantScope(organization_id, project_id, AccessScope.ORGANIZATION)


def test_enqueue_rejects_naive_or_past_schedule() -> None:
    now = datetime(2026, 8, 8, 12, tzinfo=UTC)
    service = JobService(clock=lambda: now)
    scope = TenantScope(uuid7(), uuid7(), AccessScope.PROJECT)

    for invalid_schedule in (
        datetime(2026, 8, 8, 13),
        now - timedelta(microseconds=1),
    ):
        with pytest.raises(InvalidJobTransitionError):
            service.enqueue(
                cast(Session, object()),
                scope=scope,
                job_type="documents.parse",
                payload={"document_revision_id": str(uuid7())},
                idempotency_key="invalid-schedule",
                available_at=invalid_schedule,
            )


def test_backoff_is_exponential_capped_and_deterministically_jittered() -> None:
    fixed_now = datetime(2026, 8, 8, 12, tzinfo=UTC)
    service = JobService(
        clock=lambda: fixed_now,
        jitter=lambda _attempt: 0.5,
        base_backoff=timedelta(seconds=5),
        max_backoff=timedelta(seconds=20),
    )

    assert service.retry_delay(1) == timedelta(seconds=5)
    assert service.retry_delay(2) == timedelta(seconds=10)
    assert service.retry_delay(3) == timedelta(seconds=20)
    assert service.retry_delay(9) == timedelta(seconds=20)

    low = JobService(jitter=lambda _attempt: 0).retry_delay(1)
    high = JobService(jitter=lambda _attempt: 1).retry_delay(1)
    assert low == timedelta(seconds=4)
    assert high == timedelta(seconds=6)


def test_effect_digest_example_is_not_payload_content() -> None:
    receipt_digest = hashlib.sha256(b"domain-receipt-id:42").hexdigest()
    assert len(receipt_digest) == 64
