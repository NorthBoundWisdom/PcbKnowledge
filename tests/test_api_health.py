from typing import Literal

from fastapi import HTTPException
from fastapi.testclient import TestClient

from pcbknowledge.api import create_app
from pcbknowledge.readiness import ReadinessCheck, ReadinessReport


class StubProbe:
    def __init__(self, *, ready: bool) -> None:
        self.ready = ready

    async def check(self) -> ReadinessReport:
        status: Literal["ok", "failed"] = "ok" if self.ready else "failed"
        return ReadinessReport(
            ready=self.ready,
            checks=(ReadinessCheck(name="database", status=status),),
        )


def test_healthz_is_liveness_only() -> None:
    with TestClient(create_app(readiness_probe=StubProbe(ready=False))) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "alive",
        "service": "pcbknowledge-api",
        "version": "0.1.0",
    }


def test_readyz_succeeds_only_when_probe_succeeds() -> None:
    with TestClient(create_app(readiness_probe=StubProbe(ready=True))) as client:
        response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": [{"name": "database", "status": "ok", "detail": None}],
    }


def test_readyz_failure_is_problem_details() -> None:
    with TestClient(create_app(readiness_probe=StubProbe(ready=False))) as client:
        response = client.get("/readyz")

    assert response.status_code == 503
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "urn:pcbknowledge:problem:not-ready",
        "title": "Service unavailable",
        "status": 503,
        "detail": "PcbKnowledge is not ready to serve dependency-backed requests.",
        "instance": "/readyz",
        "checks": [{"name": "database", "status": "failed", "detail": None}],
    }


def test_framework_404_is_also_problem_details() -> None:
    with TestClient(create_app(readiness_probe=StubProbe(ready=True))) as client:
        response = client.get("/not-an-endpoint")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["instance"] == "/not-an-endpoint"


def test_metrics_are_available_but_not_part_of_public_openapi() -> None:
    with TestClient(create_app(readiness_probe=StubProbe(ready=True))) as client:
        response = client.get("/metrics")
        openapi = client.get("/openapi.json").json()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert b"pcbknowledge_http_requests_total" in response.content
    assert "/metrics" not in openapi["paths"]


def test_observability_reuses_only_safe_request_ids() -> None:
    application = create_app(
        readiness_probe=StubProbe(ready=True),
        enable_observability=True,
    )
    with TestClient(application) as client:
        accepted = client.get("/healthz", headers={"x-request-id": "trusted-request.1"})
        replaced = client.get("/healthz", headers={"x-request-id": "unsafe request value"})

    assert accepted.headers["x-request-id"] == "trusted-request.1"
    assert replaced.headers["x-request-id"] != "unsafe request value"
    assert len(replaced.headers["x-request-id"]) == 32


def test_framework_authentication_header_survives_problem_conversion() -> None:
    application = create_app(readiness_probe=StubProbe(ready=True))

    @application.get("/protected-for-test")
    async def protected_for_test() -> None:
        raise HTTPException(
            status_code=401,
            detail="Authentication is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    with TestClient(application) as client:
        response = client.get("/protected-for-test")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.headers["cache-control"] == "no-store"
