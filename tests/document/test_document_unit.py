"""Hermetic contracts, projections, and verifier-boundary tests."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import timedelta
from types import SimpleNamespace
from typing import cast
from urllib.request import Request as UrlRequest

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from pcbknowledge.api import create_app
from pcbknowledge.document.contracts import (
    CompleteUploadSessionRequest,
    CreateUploadSessionRequest,
    UploadSessionProjectionState,
)
from pcbknowledge.document.errors import (
    InvalidUploadJobError,
    UploadSessionConflictError,
    UploadSessionStateError,
)
from pcbknowledge.document.repository import UploadSessionView
from pcbknowledge.document.service import _browser_upload_headers, _project_upload_state
from pcbknowledge.document.verifier import (
    ClaimedUpload,
    VerifyUploadPayload,
    _validate_job,
    run_health_check,
)
from pcbknowledge.platform.config import ObjectStorageSettings, Settings
from pcbknowledge.platform.http.authentication import (
    authenticate_request,
    request_database_session,
)
from pcbknowledge.platform.identity.types import Principal, PrincipalKind, Role
from pcbknowledge.platform.ids import new_uuid7
from pcbknowledge.platform.jobs import AccessScope, KnowledgeJob, TenantScope
from pcbknowledge.platform.storage import SeaweedFsS3Adapter
from pcbknowledge.platform.storage.adapter import S3Client
from pcbknowledge.platform.time import utc_now


class _Body:
    def __init__(self, value: bytes) -> None:
        self._value = value
        self._offset = 0

    def read(self, amount: int | None = None) -> bytes:
        if amount is None:
            amount = len(self._value)
        result = self._value[self._offset : self._offset + amount]
        self._offset += len(result)
        return result

    def close(self) -> None:
        return None


class _MemoryS3:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.put_buckets: list[str] = []
        self.cors: list[object] = []

    def put_object(self, **kwargs: object) -> object:
        bucket = cast(str, kwargs["Bucket"])
        key = cast(str, kwargs["Key"])
        body = cast(bytes, kwargs["Body"])
        self.put_buckets.append(bucket)
        self.objects[(bucket, key)] = body
        return {}

    def get_object(self, **kwargs: object) -> Mapping[str, object]:
        bucket = cast(str, kwargs["Bucket"])
        key = cast(str, kwargs["Key"])
        value = self.objects[(bucket, key)]
        return {"Body": _Body(value), "ETag": "qualified-etag"}

    def delete_object(self, **kwargs: object) -> object:
        bucket = cast(str, kwargs["Bucket"])
        key = cast(str, kwargs["Key"])
        self.objects.pop((bucket, key), None)
        return {}

    def put_bucket_cors(self, **kwargs: object) -> object:
        self.cors.append(kwargs)
        return {}


class _CorsNotImplementedError(Exception):
    def __init__(self) -> None:
        self.response = {
            "Error": {"Code": "NotImplemented"},
            "ResponseMetadata": {"HTTPStatusCode": 501},
        }


class _CorsQualificationS3(_MemoryS3):
    def __init__(self, endpoint: str) -> None:
        super().__init__()
        self.endpoint = endpoint
        self.presign_calls = 0

    def put_bucket_cors(self, **kwargs: object) -> object:
        raise _CorsNotImplementedError

    def generate_presigned_url(
        self,
        ClientMethod: str,
        Params: Mapping[str, object],
        ExpiresIn: int,
        HttpMethod: str | None = None,
    ) -> str:
        self.presign_calls += 1
        return f"{self.endpoint}/qualified?signature=redacted"


class _CorsResponse:
    status = 200

    def __init__(self) -> None:
        self.headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }

    def __enter__(self) -> _CorsResponse:
        return self

    def __exit__(self, *_arguments: object) -> None:
        return None


def _adapter(client: _MemoryS3) -> SeaweedFsS3Adapter:
    return SeaweedFsS3Adapter(
        internal_client=cast(S3Client, client),
        presign_client=cast(S3Client, client),
        bucket="pcbknowledge-content-test",
        staging_bucket="pcbknowledge-staging-test",
        allow_content_write=True,
    )


def test_upload_contract_is_pdf_only_bounded_and_server_hash_optional() -> None:
    valid = {
        "project_id": new_uuid7(),
        "access_scope_id": new_uuid7(),
        "license_policy_id": new_uuid7(),
        "source_organization_id": new_uuid7(),
        "title": "  Datasheet  ",
        "revision_label": " A ",
        "original_filename": " datasheet.pdf ",
        "byte_size": 268_435_456,
    }
    request = CreateUploadSessionRequest.model_validate(valid)
    assert request.title == "Datasheet"
    assert request.revision_label == "A"
    assert request.original_filename == "datasheet.pdf"
    assert CompleteUploadSessionRequest().expected_sha256 is None

    with pytest.raises(ValidationError):
        CreateUploadSessionRequest.model_validate({**valid, "byte_size": 268_435_457})
    with pytest.raises(ValidationError):
        CreateUploadSessionRequest.model_validate({**valid, "media_type": "text/plain"})
    with pytest.raises(ValidationError):
        CreateUploadSessionRequest.model_validate({**valid, "title": "line\nbreak"})
    with pytest.raises(ValidationError):
        CompleteUploadSessionRequest(expected_sha256="0" * 63)


def test_browser_upload_contract_never_requires_forbidden_content_length() -> None:
    assert _browser_upload_headers(
        {"Content-Type": "application/pdf", "Content-Length": "123"}
    ) == {"Content-Type": "application/pdf"}


@pytest.mark.parametrize(
    ("upload_state", "job_state", "attempts", "expected"),
    [
        ("RESERVED", None, 0, UploadSessionProjectionState.RESERVED),
        ("QUEUED", "READY", 0, UploadSessionProjectionState.QUEUED),
        ("QUEUED", "RUNNING", 1, UploadSessionProjectionState.VERIFYING),
        ("QUEUED", "READY", 1, UploadSessionProjectionState.RETRYING),
        ("STORED", "COMPLETED", 1, UploadSessionProjectionState.STORED),
        ("FAILED", "DEAD_LETTER", 1, UploadSessionProjectionState.FAILED),
    ],
)
def test_upload_projection_reports_only_observable_durable_state(
    upload_state: str,
    job_state: str | None,
    attempts: int,
    expected: UploadSessionProjectionState,
) -> None:
    upload = SimpleNamespace(state=upload_state, failure_code="UPLOAD_NOT_PDF")
    reservation = SimpleNamespace(
        state="PENDING",
        expires_at=utc_now() + timedelta(minutes=5),
    )
    job = (
        None
        if job_state is None
        else SimpleNamespace(
            state=job_state,
            attempts=attempts,
            last_failure_code="OBJECT_STORE_UNAVAILABLE" if attempts else None,
        )
    )
    projected, _failure = _project_upload_state(
        cast(UploadSessionView, SimpleNamespace(upload=upload, reservation=reservation, job=job))
    )
    assert projected is expected


def test_verifier_fencing_rejects_wrong_owner_and_expired_lease() -> None:
    scope = TenantScope(new_uuid7(), new_uuid7(), AccessScope.PROJECT)
    job_id = new_uuid7()
    upload_id = new_uuid7()
    claim = ClaimedUpload(scope=scope, job_id=job_id)
    job = SimpleNamespace(
        id=job_id,
        job_type="document.intake.verify",
        state="RUNNING",
        lease_owner="verifier-a",
        lease_expires_at=utc_now() + timedelta(minutes=5),
        attempts=1,
        payload={"upload_session_id": str(upload_id)},
    )
    payload = _validate_job(cast(KnowledgeJob, job), claim, worker_id="verifier-a")
    assert payload == VerifyUploadPayload(upload_session_id=upload_id)

    job.lease_owner = "verifier-b"
    with pytest.raises(InvalidUploadJobError):
        _validate_job(cast(KnowledgeJob, job), claim, worker_id="verifier-a")
    job.lease_owner = "verifier-a"
    job.lease_expires_at = utc_now() - timedelta(seconds=1)
    with pytest.raises(InvalidUploadJobError):
        _validate_job(cast(KnowledgeJob, job), claim, worker_id="verifier-a")


def test_verifier_storage_probe_never_writes_or_lists_permanent_bucket() -> None:
    client = _MemoryS3()
    adapter = _adapter(client)
    adapter.probe_verifier_access()
    assert client.put_buckets == ["pcbknowledge-staging-test"]
    assert client.objects == {}


def test_staging_cors_is_exact_and_put_only() -> None:
    client = _MemoryS3()
    adapter = _adapter(client)
    adapter.configure_staging_cors(
        allowed_origins=("http://localhost:8080", "http://127.0.0.1:4173")
    )
    assert client.cors == [
        {
            "Bucket": "pcbknowledge-staging-test",
            "CORSConfiguration": {
                "CORSRules": [
                    {
                        "AllowedOrigins": [
                            "http://localhost:8080",
                            "http://127.0.0.1:4173",
                        ],
                        "AllowedMethods": ["PUT"],
                        "AllowedHeaders": ["Content-Type"],
                        "ExposeHeaders": ["ETag"],
                        "MaxAgeSeconds": 600,
                    }
                ]
            },
        }
    ]
    with pytest.raises(ValueError):
        adapter.configure_staging_cors(allowed_origins=("*",))


def test_external_cors_qualification_uses_the_container_internal_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    internal = _CorsQualificationS3("http://seaweedfs:8333")
    browser = _CorsQualificationS3("http://localhost:18333")
    requested_urls: list[str] = []

    def open_request(request: UrlRequest, *, timeout: int) -> _CorsResponse:
        requested_urls.append(request.full_url)
        assert timeout == 10
        return _CorsResponse()

    monkeypatch.setattr("pcbknowledge.platform.storage.adapter.urlopen", open_request)
    adapter = SeaweedFsS3Adapter(
        internal_client=cast(S3Client, internal),
        presign_client=cast(S3Client, browser),
        bucket="pcbknowledge-content-test",
        staging_bucket="pcbknowledge-staging-test",
    )

    adapter.configure_staging_cors(allowed_origins=("http://localhost:18080",))

    assert internal.presign_calls == 1
    assert browser.presign_calls == 0
    assert requested_urls == ["http://seaweedfs:8333/qualified?signature=redacted"]


def test_health_check_requires_verifier_mode_and_sanitizes_failure() -> None:
    wrong_mode = cast(ObjectStorageSettings, SimpleNamespace(access_mode="admin"))
    result = run_health_check(
        settings_loader=lambda: cast(Settings, SimpleNamespace()),
        storage_settings_loader=lambda: wrong_mode,
        database_probe=lambda _settings: None,
        storage_probe=lambda _settings: None,
    )
    assert result.status == "not_ready"
    assert result.reason == "required verifier configuration is missing or invalid"
    assert "secret" not in result.model_dump_json().casefold()


def test_document_openapi_declares_replay_and_problem_statuses() -> None:
    paths = create_app().openapi()["paths"]
    create_responses = paths["/upload-sessions"]["post"]["responses"]
    assert set(create_responses) == {
        "200",
        "201",
        "401",
        "403",
        "409",
        "413",
        "422",
        "503",
    }
    complete_responses = paths["/upload-sessions/{upload_session_id}/complete"]["post"]["responses"]
    assert set(complete_responses) == {"200", "202", "401", "404", "409", "422"}
    for response in (create_responses["200"], complete_responses["200"]):
        schema = response["content"]["application/json"]["schema"]
        assert schema["$ref"].endswith("/UploadSessionResponse")


def test_complete_route_maps_durable_staging_conflict_to_problem_409() -> None:
    project_id = new_uuid7()
    principal = Principal(
        subject_id=new_uuid7(),
        issuer="https://issuer.invalid",
        subject="curator",
        kind=PrincipalKind.HUMAN,
        organization_id=new_uuid7(),
        project_roles={project_id: frozenset({Role.DATA_CURATOR})},
    )

    class _ConflictService:
        @staticmethod
        def complete_upload_session(*_args: object, **_kwargs: object) -> object:
            raise UploadSessionStateError()

    def session_dependency() -> Iterator[Session]:
        yield cast(Session, object())

    app = create_app()
    app.dependency_overrides[request_database_session] = session_dependency
    app.dependency_overrides[authenticate_request] = lambda: principal
    app.state.document_service_factory = lambda _request, _principal: _ConflictService()
    response = TestClient(app).post(
        f"/upload-sessions/{new_uuid7()}/complete",
        json={},
    )
    assert response.status_code == 409
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["type"] == "urn:pcbknowledge:problem:upload-conflict"


def test_create_route_maps_revision_intent_conflict_to_problem_409() -> None:
    project_id = new_uuid7()
    principal = Principal(
        subject_id=new_uuid7(),
        issuer="https://issuer.invalid",
        subject="curator",
        kind=PrincipalKind.HUMAN,
        organization_id=new_uuid7(),
        project_roles={project_id: frozenset({Role.DATA_CURATOR})},
    )

    class _ConflictService:
        @staticmethod
        def create_upload_session(*_args: object, **_kwargs: object) -> object:
            raise UploadSessionConflictError()

    def session_dependency() -> Iterator[Session]:
        yield cast(Session, object())

    app = create_app()
    app.dependency_overrides[request_database_session] = session_dependency
    app.dependency_overrides[authenticate_request] = lambda: principal
    app.state.document_service_factory = lambda _request, _principal: _ConflictService()
    response = TestClient(app).post(
        "/upload-sessions",
        headers={"Idempotency-Key": "revision-conflict"},
        json={
            "project_id": str(project_id),
            "access_scope_id": str(new_uuid7()),
            "license_policy_id": str(new_uuid7()),
            "source_organization_id": str(new_uuid7()),
            "document_id": str(new_uuid7()),
            "revision_label": "B",
            "original_filename": "revision-b.pdf",
            "byte_size": 128,
        },
    )
    assert response.status_code == 409
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["type"] == "urn:pcbknowledge:problem:upload-conflict"
