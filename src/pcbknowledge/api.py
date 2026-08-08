"""FastAPI process boundary for PcbKnowledge."""

from typing import Literal

import uvicorn
from fastapi import FastAPI, Request
from pydantic import BaseModel

from pcbknowledge import __version__
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


_READINESS_ERROR_RESPONSE = {
    "description": "The service or one of its required dependencies is not ready.",
    "content": {
        "application/problem+json": {
            "schema": ProblemDetail.model_json_schema(),
        },
    },
}


def create_app(*, readiness_probe: ReadinessProbe | None = None) -> FastAPI:
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

    return application


app = create_app()


def main() -> None:
    """Run the development ASGI server; deployment invokes the same ASGI target."""

    uvicorn.run("pcbknowledge.api:app", host="0.0.0.0", port=8000)
