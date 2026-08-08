from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import BaseModel, ValidationError

from pcbknowledge.platform.ids import UUID7, is_uuid7, new_uuid7, require_uuid7
from pcbknowledge.platform.time import UTCDateTime, ensure_utc, parse_rfc3339


class IdentifierDto(BaseModel):
    id: UUID7


class TimestampDto(BaseModel):
    occurred_at: UTCDateTime


def test_uuid7_generation_and_dto_validation() -> None:
    identifier = new_uuid7()

    assert is_uuid7(identifier)
    assert IdentifierDto(id=str(identifier)).id == identifier
    with pytest.raises(ValueError):
        require_uuid7(uuid4())
    with pytest.raises(ValidationError):
        IdentifierDto(id=uuid4())


def test_utc_constraint_rejects_naive_and_normalizes_offsets() -> None:
    with pytest.raises(ValueError):
        ensure_utc(datetime(2026, 8, 8, 12, 0, 0))

    china_time = datetime(2026, 8, 8, 20, 0, 0, tzinfo=timezone(timedelta(hours=8)))
    dto = TimestampDto(occurred_at=china_time)

    assert dto.occurred_at == datetime(2026, 8, 8, 12, 0, 0, tzinfo=UTC)
    assert dto.model_dump_json() == '{"occurred_at":"2026-08-08T12:00:00.000000Z"}'


def test_rfc3339_parser_requires_time_and_timezone() -> None:
    assert parse_rfc3339("2026-08-08T12:00:00Z") == datetime(2026, 8, 8, 12, 0, 0, tzinfo=UTC)
    with pytest.raises(ValueError):
        parse_rfc3339("2026-08-08")
    with pytest.raises(ValueError):
        parse_rfc3339("2026-08-08T12:00:00")
    with pytest.raises(ValidationError):
        TimestampDto.model_validate({"occurred_at": "2026-08-08 12:00:00Z"})
