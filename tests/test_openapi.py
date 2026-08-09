from pathlib import Path

from pcbknowledge.api import app
from pcbknowledge.contracts.openapi import export_openapi, render_openapi

CONTRACT = Path("packages/contracts/openapi/pcbknowledge.openapi.json")


def test_committed_openapi_is_current() -> None:
    assert export_openapi(CONTRACT, check=True)


def test_openapi_render_is_deterministic() -> None:
    assert render_openapi(app) == render_openapi(app)
    assert render_openapi(app).endswith("\n")


def test_openapi_declares_health_session_and_document_intake_operations() -> None:
    document = app.openapi()

    assert document["openapi"].startswith("3.1.")
    assert document["servers"] == [
        {"url": "/api/v1", "description": "Versioned API gateway"},
    ]
    assert set(document["paths"]) == {
        "/document-revisions/{revision_id}",
        "/document-revisions/{revision_id}/original-download",
        "/documents",
        "/healthz",
        "/intake/options",
        "/readyz",
        "/session",
        "/upload-sessions",
        "/upload-sessions/{upload_session_id}",
        "/upload-sessions/{upload_session_id}/complete",
    }
    readiness_error = document["paths"]["/readyz"]["get"]["responses"]["503"]
    assert set(readiness_error["content"]) == {"application/problem+json"}
    session_operation = document["paths"]["/session"]["get"]
    assert session_operation["security"] == [{"HTTPBearer": []}]
    assert session_operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/SessionResponse"
    }
