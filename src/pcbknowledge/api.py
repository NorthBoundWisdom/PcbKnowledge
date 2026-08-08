"""FastAPI process boundary for PcbKnowledge."""

from typing import Literal

import uvicorn
from fastapi import FastAPI, Request, Response
from pydantic import BaseModel, ConfigDict

from pcbknowledge import __version__
from pcbknowledge.platform.audit import AuditEventDraft, AuditOutcome, AuditWriter
from pcbknowledge.platform.config import get_observability_settings
from pcbknowledge.platform.http import PrincipalDependency, SessionDependency
from pcbknowledge.platform.identity.types import PrincipalKind, Role
from pcbknowledge.platform.ids import UUID7
from pcbknowledge.platform.observability import install_observability
from pcbknowledge.platform.observability.context import current_request_context
from pcbknowledge.platform.observability.metrics import prometheus_response
from pcbknowledge.platform.time import UTCDateTime, utc_now
from pcbknowledge.readiness import ApplicationReadinessProbe, ReadinessCheck, ReadinessProbe
from pcbknowledge.shared.errors import ProblemDetail, ProblemException, install_problem_handlers


class HealthResponse(BaseModel):
    """Process liveness response; it deliberately makes no dependency claim."""

    status: Literal["alive"] = "alive"
    service: Literal["pcbknowledge-api"] = "pcbknowledge-api"
    version: str


class ReadyResponse(BaseModel):
    """Successful readiness response after all dependency probes pass."""

    status: Literal["ready"] = "ready"
    checks: tuple[ReadinessCheck, ...]


class SessionProject(BaseModel):
    """One explicit project grant from the trusted external-subject mapping."""

    model_config = ConfigDict(frozen=True)

    id: UUID7
    roles: tuple[Role, ...]


class SessionResponse(BaseModel):
    """Trusted current-session projection; it never echoes bearer claims or tokens."""

    model_config = ConfigDict(frozen=True)

    subject_id: UUID7
    subject_kind: PrincipalKind
    organization_id: UUID7
    organization_roles: tuple[Role, ...]
    projects: tuple[SessionProject, ...]
    authenticated_at: UTCDateTime


def _problem_response(description: str) -> dict[str, object]:
    return {
        "description": description,
        "content": {
            "application/problem+json": {
                "schema": ProblemDetail.model_json_schema(),
            },
        },
    }


_READINESS_ERROR_RESPONSE = _problem_response(
    "The service or one of its required dependencies is not ready."
)


def create_app(
    *,
    readiness_probe: ReadinessProbe | None = None,
    enable_observability: bool = False,
) -> FastAPI:
    """Build an API application without connecting to infrastructure at import time."""

    application = FastAPI(
        title="PcbKnowledge API",
        summary="Evidence-first PCB engineering knowledge service",
        version=__version__,
        openapi_version="3.1.0",
        servers=[{"url": "/api/v1", "description": "Versioned API gateway"}],
    )
    install_problem_handlers(application)
    application.state.readiness_probe = readiness_probe or ApplicationReadinessProbe()

    if enable_observability:
        telemetry = get_observability_settings()
        install_observability(
            application,
            service_name=telemetry.service_name,
            otlp_endpoint=(
                str(telemetry.otel_exporter_otlp_endpoint)
                if telemetry.otel_exporter_otlp_endpoint is not None
                else None
            ),
        )

    @application.get(
        "/healthz",
        operation_id="get_liveness",
        response_model=HealthResponse,
        tags=["operations"],
    )
    async def get_liveness() -> HealthResponse:
        return HealthResponse(version=__version__)

    @application.get(
        "/readyz",
        operation_id="get_readiness",
        response_model=ReadyResponse,
        responses={503: _READINESS_ERROR_RESPONSE},
        tags=["operations"],
    )
    async def get_readiness(request: Request) -> ReadyResponse:
        probe: ReadinessProbe = request.app.state.readiness_probe
        report = await probe.check()
        if not report.ready:
            raise ProblemException(
                status=503,
                title="Service unavailable",
                detail="PcbKnowledge is not ready to serve dependency-backed requests.",
                type_uri="urn:pcbknowledge:problem:not-ready",
                extensions={
                    "checks": [check.model_dump(mode="json") for check in report.checks],
                },
            )
        return ReadyResponse(checks=report.checks)

    @application.get("/metrics", include_in_schema=False)
    async def get_metrics() -> Response:
        """Expose process metrics only on the internal API network."""

        return prometheus_response()

    @application.get(
        "/session",
        operation_id="get_current_session",
        response_model=SessionResponse,
        responses={
            401: _problem_response("A valid bearer token is required."),
            503: _problem_response("The configured identity provider is unavailable."),
        },
        tags=["identity"],
    )
    def get_current_session(
        request: Request,
        principal: PrincipalDependency,
        session: SessionDependency,
    ) -> SessionResponse:
        context = current_request_context()
        audit_writer = getattr(request.app.state, "audit_writer", None) or AuditWriter()
        audit_writer.append(
            session,
            AuditEventDraft(
                organization_id=principal.organization_id,
                action="identity.session.authenticate",
                resource_type="external_subject",
                resource_id=principal.subject_id,
                outcome=AuditOutcome.SUCCEEDED,
                request_id=context.request_id if context is not None else None,
                detail={"subject_kind": principal.kind.value},
            ),
            principal=principal,
        )
        return SessionResponse(
            subject_id=principal.subject_id,
            subject_kind=principal.kind,
            organization_id=principal.organization_id,
            organization_roles=tuple(sorted(principal.organization_roles)),
            projects=tuple(
                SessionProject(id=project_id, roles=tuple(sorted(roles)))
                for project_id, roles in sorted(
                    principal.project_roles.items(), key=lambda item: item[0].int
                )
            ),
            authenticated_at=utc_now(),
        )

    return application


app = create_app(enable_observability=True)


def main() -> None:
    """Run the development ASGI server; deployment invokes the same ASGI target."""

    uvicorn.run("pcbknowledge.api:app", host="0.0.0.0", port=8000)
