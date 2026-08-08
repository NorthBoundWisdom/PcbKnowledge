"""Context-local correlation identifiers safe for logs and audit metadata."""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RequestContext:
    """Non-secret identifiers associated with one request or worker operation."""

    request_id: str
    trace_id: str
    subject_id: UUID | None = None
    organization_id: UUID | None = None
    project_id: UUID | None = None
    job_id: UUID | None = None
    document_revision_id: UUID | None = None
    agent_run_id: str | None = None

    def with_identity(
        self,
        *,
        subject_id: UUID,
        organization_id: UUID,
        project_id: UUID | None,
    ) -> RequestContext:
        """Return a copy enriched only after authentication and authorization."""

        return replace(
            self,
            subject_id=subject_id,
            organization_id=organization_id,
            project_id=project_id,
        )


_request_context: ContextVar[RequestContext | None] = ContextVar(
    "pcbknowledge_request_context",
    default=None,
)


def current_request_context() -> RequestContext | None:
    """Return the context bound to the current async task, if any."""

    return _request_context.get()


def enrich_request_context(
    *,
    subject_id: UUID,
    organization_id: UUID,
    project_id: UUID | None,
) -> RequestContext:
    """Attach trusted authorization identifiers to the current request context."""

    current = _request_context.get()
    if current is None:
        raise RuntimeError("no request context is bound")
    enriched = current.with_identity(
        subject_id=subject_id,
        organization_id=organization_id,
        project_id=project_id,
    )
    _request_context.set(enriched)
    return enriched


@contextmanager
def bind_request_context(context: RequestContext) -> Iterator[None]:
    """Bind a context for a delimited request/worker scope and reliably reset it."""

    token = _request_context.set(context)
    try:
        yield
    finally:
        _request_context.reset(token)
