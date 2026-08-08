import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from pcbknowledge.platform.audit import (
    AuditEventDraft,
    AuditOutcome,
    AuditTransactionRequiredError,
    AuditWriter,
)
from pcbknowledge.platform.ids import new_uuid7


def _draft(**overrides: object) -> AuditEventDraft:
    values: dict[str, object] = {
        "organization_id": new_uuid7(),
        "action": "document.metadata.update",
        "resource_type": "document_revision",
        "resource_id": new_uuid7(),
        "outcome": AuditOutcome.SUCCEEDED,
        "detail": {"reason_code": "CURATOR_CONFIRMED", "field_count": 2},
    }
    values.update(overrides)
    return AuditEventDraft.model_validate(values)


@pytest.mark.parametrize(
    "detail",
    [
        {"token": "credential"},
        {"nested": {"authorization": "Bearer credential"}},
        {"source_text": "copied document prose"},
        {"payload": {"arbitrary": "object"}},
        {"accessToken": "credential"},
        {"refreshToken": "credential"},
        {"clientSecret": "credential"},
        {"sourceText": "copied document prose"},
        {"documentBytes": "encoded source"},
    ],
)
def test_audit_detail_rejects_sensitive_keys(detail: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _draft(detail=detail)


def test_audit_detail_rejects_unbounded_or_non_json_metadata() -> None:
    with pytest.raises(ValidationError):
        _draft(detail={"note": "x" * 513})
    with pytest.raises(ValidationError):
        _draft(detail={"level1": {"level2": {"level3": {"level4": "too deep"}}}})
    with pytest.raises(ValidationError):
        _draft(detail={"value": object()})


def test_audit_writer_requires_caller_owned_transaction() -> None:
    session = Session()
    try:
        with pytest.raises(AuditTransactionRequiredError):
            AuditWriter().append(session, _draft(), principal=None)
    finally:
        session.close()


@pytest.mark.parametrize(
    "mutation",
    [
        {"token": "credential"},
        {"note": "x" * 10_000},
    ],
)
def test_audit_writer_revalidates_detail_after_nested_mutation(
    mutation: dict[str, object],
) -> None:
    draft = _draft()
    draft.detail.update(mutation)
    session = Session()
    try:
        with session.begin(), pytest.raises(ValidationError):
            AuditWriter().append(session, draft, principal=None)
    finally:
        session.close()
