from pathlib import Path

from pcbknowledge.api import app
from pcbknowledge.contracts.openapi import export_openapi, render_openapi

CONTRACT = Path("packages/contracts/openapi/pcbknowledge.openapi.json")


def test_committed_openapi_is_current() -> None:
    assert export_openapi(CONTRACT, check=True)


def test_openapi_render_is_deterministic() -> None:
    assert render_openapi(app) == render_openapi(app)
    assert render_openapi(app).endswith("\n")


def test_openapi_declares_31_and_only_health_operations() -> None:
    document = app.openapi()

    assert document["openapi"].startswith("3.1.")
    assert document["servers"] == [
        {"url": "/api/v1", "description": "Versioned API gateway"},
    ]
    assert set(document["paths"]) == {"/healthz", "/readyz"}
    readiness_error = document["paths"]["/readyz"]["get"]["responses"]["503"]
    assert set(readiness_error["content"]) == {"application/problem+json"}
