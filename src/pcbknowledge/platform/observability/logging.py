"""JSON logging with correlation fields and conservative credential redaction."""

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

from pcbknowledge.platform.observability.context import current_request_context

_BEARER_PATTERN = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")
_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)(\b(?:access[_-]?token|refresh[_-]?token|password|secret|api[_-]?key)\b\s*[:=]\s*)"
    r"(?:\"[^\"]*\"|'[^']*'|[^\s,;}]+)"
)


def redact_log_value(value: object) -> str:
    """Render a log value while removing common credential forms.

    Callers must still avoid logging source text or confidential payloads. This
    is a final safety net, not permission to pass arbitrary request data.
    """

    rendered = str(value)
    rendered = _BEARER_PATTERN.sub("Bearer [REDACTED]", rendered)
    return _SECRET_ASSIGNMENT_PATTERN.sub(r"\1[REDACTED]", rendered)


class JsonLogFormatter(logging.Formatter):
    """Emit one stable JSON object per record without serializing record extras."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_log_value(record.getMessage()),
        }
        context = current_request_context()
        if context is not None:
            payload.update(
                {
                    "request_id": context.request_id,
                    "trace_id": context.trace_id,
                    "user_or_service_subject": _optional_id(context.subject_id),
                    "organization_id": _optional_id(context.organization_id),
                    "project_id": _optional_id(context.project_id),
                    "job_id": _optional_id(context.job_id),
                    "document_revision_id": _optional_id(context.document_revision_id),
                    "agent_run_id": context.agent_run_id,
                }
            )
        if record.exc_info is not None and record.exc_info[0] is not None:
            payload["exception_type"] = record.exc_info[0].__name__
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _optional_id(value: object | None) -> str | None:
    return None if value is None else str(value)


def configure_json_logging(*, level: int = logging.INFO) -> None:
    """Configure the process root logger once for JSON stdout/stderr handlers."""

    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
