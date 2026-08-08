import json
import logging
from uuid import uuid7

from pcbknowledge.platform.observability.context import (
    RequestContext,
    bind_request_context,
    current_request_context,
    enrich_request_context,
)
from pcbknowledge.platform.observability.logging import JsonLogFormatter, redact_log_value


def test_log_redaction_removes_bearer_and_assigned_secrets() -> None:
    rendered = redact_log_value(
        "Authorization=Bearer abc.def.ghi password=hunter2 access_token='visible'"
    )

    assert "abc.def.ghi" not in rendered
    assert "hunter2" not in rendered
    assert "visible" not in rendered
    assert rendered.count("[REDACTED]") == 3


def test_json_formatter_emits_correlation_ids_without_arbitrary_extras() -> None:
    formatter = JsonLogFormatter()
    record = logging.LogRecord(
        name="pcbknowledge.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="completed %s",
        args=("safely",),
        exc_info=None,
    )
    record.confidential_payload = "must-not-be-serialized"

    with bind_request_context(RequestContext(request_id="req-1", trace_id="a" * 32)):
        payload = json.loads(formatter.format(record))

    assert payload["request_id"] == "req-1"
    assert payload["trace_id"] == "a" * 32
    assert payload["message"] == "completed safely"
    assert "must-not-be-serialized" not in json.dumps(payload)


def test_identity_enrichment_is_delimited_by_outer_request_scope() -> None:
    original = RequestContext(request_id="req-2", trace_id="b" * 32)
    with bind_request_context(original):
        enriched = enrich_request_context(
            subject_id=uuid7(),
            organization_id=uuid7(),
            project_id=uuid7(),
        )
        assert current_request_context() == enriched

    assert current_request_context() is None
