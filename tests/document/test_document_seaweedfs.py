"""Real PostgreSQL + SeaweedFS tests for the document verifier boundary."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from http.client import RemoteDisconnected
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID

import boto3  # type: ignore[import-untyped]
import pytest
from botocore.config import Config  # type: ignore[import-untyped]
from botocore.exceptions import ClientError  # type: ignore[import-untyped]
from sqlalchemy import Engine, create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from pcbknowledge.document.contracts import (
    CompleteUploadSessionRequest,
    CreateUploadSessionRequest,
    UploadSessionProjectionState,
    UploadSessionResponse,
)
from pcbknowledge.document.models import Document, DocumentRevision
from pcbknowledge.document.service import DocumentService
from pcbknowledge.document.verifier import DocumentVerifierWorker
from pcbknowledge.platform.audit import AuditWriter
from pcbknowledge.platform.authorization import (
    SourceOrganization,
    install_principal_context,
)
from pcbknowledge.platform.database.runtime import DatabaseRuntime
from pcbknowledge.platform.outbox import OutboxService
from pcbknowledge.platform.storage import (
    AuditWriterAssetReadAuditor,
    ObjectStorageService,
    PolicyStorageAuthorizer,
    SeaweedFsS3Adapter,
)
from pcbknowledge.platform.storage.adapter import S3Client
from pcbknowledge.platform.storage.keys import content_addressed_key, staging_object_key
from tests.platform_jobs.postgres_support import (
    IdentitySeed,
    require_postgres_engine,
    reset_and_seed,
)

_PDF = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
_ORIGIN = "http://localhost:8080"


@dataclass(frozen=True, slots=True)
class IntegrationEnvironment:
    app_database_dsn: str
    verifier_database_dsn: str
    endpoint: str
    public_endpoint: str
    api_access_key: str
    api_secret_key: str
    verifier_access_key: str
    verifier_secret_key: str
    admin_access_key: str
    admin_secret_key: str
    bucket: str
    staging_bucket: str


@dataclass(slots=True)
class _RecordingS3:
    client: Any
    permanent_bucket: str
    permanent_copy_calls: list[Mapping[str, object]]

    def copy_object(self, **kwargs: object) -> object:
        if kwargs.get("Bucket") == self.permanent_bucket:
            self.permanent_copy_calls.append(dict(kwargs))
        return self.client.copy_object(**kwargs)

    def __getattr__(self, name: str) -> object:
        return getattr(self.client, name)


@dataclass(frozen=True, slots=True)
class DocumentE2E:
    environment: IntegrationEnvironment
    owner_engine: Engine
    app_runtime: DatabaseRuntime
    verifier_runtime: DatabaseRuntime
    identity: IdentitySeed
    source_organization_id: UUID
    service: DocumentService
    verifier_adapter: SeaweedFsS3Adapter
    admin_client: Any
    api_client: Any
    recording_client: _RecordingS3


def _require_environment() -> IntegrationEnvironment:
    names = {
        "app_database_dsn": "PCBKNOWLEDGE_M1_APP_DATABASE_DSN",
        "verifier_database_dsn": "PCBKNOWLEDGE_M2_VERIFIER_DATABASE_DSN",
        "endpoint": "PCBKNOWLEDGE_M1_S3_ENDPOINT_URL",
        "public_endpoint": "PCBKNOWLEDGE_M1_S3_PUBLIC_ENDPOINT_URL",
        "api_access_key": "PCBKNOWLEDGE_M1_S3_ACCESS_KEY",
        "api_secret_key": "PCBKNOWLEDGE_M1_S3_SECRET_KEY",
        "verifier_access_key": "PCBKNOWLEDGE_M2_S3_VERIFIER_ACCESS_KEY",
        "verifier_secret_key": "PCBKNOWLEDGE_M2_S3_VERIFIER_SECRET_KEY",
        "admin_access_key": "PCBKNOWLEDGE_M1_S3_ADMIN_ACCESS_KEY",
        "admin_secret_key": "PCBKNOWLEDGE_M1_S3_ADMIN_SECRET_KEY",
        "bucket": "PCBKNOWLEDGE_M1_S3_BUCKET",
        "staging_bucket": "PCBKNOWLEDGE_M1_S3_STAGING_BUCKET",
    }
    values = {field: os.environ.get(name) for field, name in names.items()}
    if any(value is None for value in values.values()):
        pytest.skip("set explicit PostgreSQL and S3 integration credentials")
    environment = IntegrationEnvironment(**values)  # type: ignore[arg-type]
    for dsn in (environment.app_database_dsn, environment.verifier_database_dsn):
        url = make_url(dsn)
        if url.drivername != "postgresql+psycopg" or url.database is None:
            pytest.fail("document integration DSNs must use postgresql+psycopg")
        if not url.database.startswith("pcbknowledge_m1_test"):
            pytest.fail("refusing to mutate a non-test document database")
    return environment


def _s3_client(
    environment: IntegrationEnvironment,
    *,
    access_key: str,
    secret_key: str,
) -> Any:
    return boto3.client(
        "s3",
        endpoint_url=environment.endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="us-east-1",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def _runtime(dsn: str, *, expected_session_user: str) -> DatabaseRuntime:
    engine = create_engine(dsn, pool_pre_ping=True)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT session_user")) == expected_session_user
    return DatabaseRuntime(
        engine=engine,
        session_factory=sessionmaker(
            bind=engine,
            autoflush=False,
            expire_on_commit=False,
        ),
    )


def _empty_bucket(client: Any, bucket: str) -> None:
    response = client.list_objects_v2(Bucket=bucket)
    objects = [{"Key": item["Key"]} for item in response.get("Contents", [])]
    if objects:
        client.delete_objects(Bucket=bucket, Delete={"Objects": objects})


@pytest.fixture
def document_e2e() -> Iterator[DocumentE2E]:
    environment = _require_environment()
    owner_engine = require_postgres_engine()
    identity = reset_and_seed(owner_engine)
    source = SourceOrganization(
        organization_id=identity.organization_a,
        name="Document SeaweedFS authority",
        authority_tier="PRIMARY",
    )
    with Session(owner_engine) as session, session.begin():
        session.add(source)
        session.flush((source,))
        source_organization_id = source.id

    admin = _s3_client(
        environment,
        access_key=environment.admin_access_key,
        secret_key=environment.admin_secret_key,
    )
    for bucket in (environment.bucket, environment.staging_bucket):
        try:
            admin.create_bucket(Bucket=bucket)
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") not in {
                "BucketAlreadyExists",
                "BucketAlreadyOwnedByYou",
            }:
                raise
            _empty_bucket(admin, bucket)

    admin_adapter = SeaweedFsS3Adapter.from_credentials(
        internal_endpoint_url=environment.endpoint,
        public_endpoint_url=environment.public_endpoint,
        access_key_id=environment.admin_access_key,
        secret_access_key=environment.admin_secret_key,
        bucket=environment.bucket,
        staging_bucket=environment.staging_bucket,
        allow_content_write=True,
    )
    admin_adapter.configure_staging_cors(allowed_origins=(_ORIGIN,))

    api_client = _s3_client(
        environment,
        access_key=environment.api_access_key,
        secret_key=environment.api_secret_key,
    )
    api_adapter = SeaweedFsS3Adapter.from_credentials(
        internal_endpoint_url=environment.endpoint,
        public_endpoint_url=environment.public_endpoint,
        access_key_id=environment.api_access_key,
        secret_access_key=environment.api_secret_key,
        bucket=environment.bucket,
        staging_bucket=environment.staging_bucket,
    )
    verifier_client = _s3_client(
        environment,
        access_key=environment.verifier_access_key,
        secret_key=environment.verifier_secret_key,
    )
    recording = _RecordingS3(
        client=verifier_client,
        permanent_bucket=environment.bucket,
        permanent_copy_calls=[],
    )
    verifier_adapter = SeaweedFsS3Adapter(
        internal_client=cast(S3Client, recording),
        presign_client=cast(S3Client, recording),
        bucket=environment.bucket,
        staging_bucket=environment.staging_bucket,
        allow_content_write=True,
    )
    verifier_adapter.probe_verifier_access()

    audit = AuditWriter()
    storage = ObjectStorageService(
        adapter=api_adapter,
        authorizer=PolicyStorageAuthorizer(identity.principal_a),
        auditor=AuditWriterAssetReadAuditor(audit, identity.principal_a),
        outbox=OutboxService(jitter=lambda _attempt: 0.5),
    )
    app_runtime = _runtime(
        environment.app_database_dsn,
        expected_session_user="pcbknowledge_app",
    )
    verifier_runtime = _runtime(
        environment.verifier_database_dsn,
        expected_session_user="pcbknowledge_verifier",
    )
    try:
        yield DocumentE2E(
            environment=environment,
            owner_engine=owner_engine,
            app_runtime=app_runtime,
            verifier_runtime=verifier_runtime,
            identity=identity,
            source_organization_id=source_organization_id,
            service=DocumentService(storage=storage, adapter=api_adapter, audit=audit),
            verifier_adapter=verifier_adapter,
            admin_client=admin,
            api_client=api_client,
            recording_client=recording,
        )
    finally:
        app_runtime.dispose()
        verifier_runtime.dispose()
        owner_engine.dispose()
        for bucket in (environment.bucket, environment.staging_bucket):
            _empty_bucket(admin, bucket)


def _reserve(
    context: DocumentE2E,
    *,
    case: str,
    byte_size: int,
) -> UploadSessionResponse:
    request = CreateUploadSessionRequest(
        project_id=context.identity.project_a1,
        access_scope_id=context.identity.scope_a1,
        license_policy_id=context.identity.policy_a1_allow,
        source_organization_id=context.source_organization_id,
        title=f"SeaweedFS document {case}",
        document_number=f"DOC-S3-{case}",
        revision_label="A",
        original_filename=f"{case}.pdf",
        byte_size=byte_size,
    )
    with context.app_runtime.transaction() as session:
        install_principal_context(session, context.identity.principal_a)
        result = context.service.create_upload_session(
            session,
            principal=context.identity.principal_a,
            request=request,
            idempotency_key=f"document-seaweedfs-{case}",
            request_id=f"reserve-{case}",
        )
    assert result.upload is not None
    assert result.upload.headers == {"Content-Type": "application/pdf"}
    return result


def _browser_put(
    reservation: UploadSessionResponse,
    content: bytes,
    *,
    preflight: bool = False,
) -> None:
    assert reservation.upload is not None
    if preflight:
        request = Request(
            reservation.upload.url,
            method="OPTIONS",
            headers={
                "Origin": _ORIGIN,
                "Access-Control-Request-Method": "PUT",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        with urlopen(request, timeout=10) as response:
            assert response.status in {200, 204}
            assert response.headers.get("Access-Control-Allow-Origin") in {_ORIGIN, "*"}
    request = Request(
        reservation.upload.url,
        data=content,
        headers=reservation.upload.headers,
        method="PUT",
    )
    with urlopen(request, timeout=10) as response:
        assert response.status in {200, 201}


def _assert_untrusted_origin_is_denied(reservation: UploadSessionResponse) -> None:
    assert reservation.upload is not None
    request = Request(
        reservation.upload.url,
        method="OPTIONS",
        headers={
            "Origin": "https://cors-denied.invalid",
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    try:
        with urlopen(request, timeout=2) as response:
            assert response.headers.get("Access-Control-Allow-Origin") not in {
                "*",
                "https://cors-denied.invalid",
            }
    except HTTPError as error:
        assert error.code in {400, 401, 403}
    except ConnectionResetError, RemoteDisconnected, TimeoutError, URLError:
        # SeaweedFS 3.85 closes denied preflights without a valid HTTP reply.
        pass


def _complete(
    context: DocumentE2E,
    reservation: UploadSessionResponse,
    *,
    expected_sha256: str | None = None,
) -> UploadSessionResponse:
    with context.app_runtime.transaction() as session:
        install_principal_context(session, context.identity.principal_a)
        return context.service.complete_upload_session(
            session,
            principal=context.identity.principal_a,
            upload_id=reservation.id,
            request=CompleteUploadSessionRequest(expected_sha256=expected_sha256),
            request_id=f"complete-{reservation.id}",
        )


def _worker(context: DocumentE2E) -> DocumentVerifierWorker:
    return DocumentVerifierWorker(
        database=context.verifier_runtime,
        adapter=context.verifier_adapter,
        worker_id="document-seaweedfs-verifier",
        jobs=None,
    )


def test_browser_upload_verifier_catalog_download_and_canonical_replay(
    document_e2e: DocumentE2E,
) -> None:
    context = document_e2e
    digest = hashlib.sha256(_PDF).hexdigest()
    first = _reserve(context, case="normal-1", byte_size=len(_PDF))
    _browser_put(first, _PDF, preflight=True)
    queued = _complete(context, first)
    assert queued.state is UploadSessionProjectionState.QUEUED

    worker = _worker(context)
    assert worker.run_once() == 1
    assert len(context.recording_client.permanent_copy_calls) == 1

    with context.app_runtime.transaction() as session:
        install_principal_context(session, context.identity.principal_a)
        stored = context.service.get_upload_session(
            session,
            principal=context.identity.principal_a,
            upload_id=first.id,
        )
        listing = context.service.list_documents(
            session,
            principal=context.identity.principal_a,
            project_id=context.identity.project_a1,
            cursor=None,
            limit=25,
        )
        metadata = context.service.get_revision_metadata(
            session,
            principal=context.identity.principal_a,
            revision_id=first.revision_id,
        )
        download = context.service.create_original_download(
            session,
            principal=context.identity.principal_a,
            revision_id=first.revision_id,
        )
    assert stored.state is UploadSessionProjectionState.STORED
    assert stored.actual_sha256 == digest
    assert len(listing.items) == 1
    assert listing.items[0].title == "SeaweedFS document normal-1"
    assert metadata.sha256 == digest
    assert metadata.state == "STORED"
    with urlopen(download.url, timeout=10) as response:
        assert response.read() == _PDF

    second = _reserve(context, case="normal-2", byte_size=len(_PDF))
    _browser_put(second, _PDF)
    _complete(context, second)
    assert worker.run_once() == 1
    assert len(context.recording_client.permanent_copy_calls) == 1

    key = content_addressed_key(context.identity.organization_a, digest)
    canonical = context.admin_client.get_object(
        Bucket=context.environment.bucket,
        Key=key,
    )["Body"].read()
    assert canonical == _PDF
    with Session(context.owner_engine) as session:
        assert session.scalar(select(func.count()).select_from(Document)) == 2
        assert session.scalar(select(func.count()).select_from(DocumentRevision)) == 2
        assert (
            session.scalar(
                text(
                    "SELECT count(*) FROM platform.object_asset "
                    "WHERE asset_kind = 'DOCUMENT_ORIGINAL'"
                )
            )
            == 1
        )
        assert (
            session.scalar(
                text(
                    "SELECT count(*) FROM audit.audit_event "
                    "WHERE action = 'document.revision.stored'"
                )
            )
            == 2
        )
    _assert_untrusted_origin_is_denied(second)


@pytest.mark.parametrize(
    ("case", "content", "declared_size", "expected_sha256", "failure_code"),
    [
        ("invalid-magic", b"not a pdf", 9, None, "UPLOAD_NOT_PDF"),
        ("size-mismatch", _PDF, len(_PDF) + 1, None, "UPLOAD_SIZE_MISMATCH"),
        ("digest-mismatch", _PDF, len(_PDF), "0" * 64, "UPLOAD_DIGEST_MISMATCH"),
    ],
)
def test_verifier_rejects_invalid_bytes_without_authoritative_artifacts(
    document_e2e: DocumentE2E,
    case: str,
    content: bytes,
    declared_size: int,
    expected_sha256: str | None,
    failure_code: str,
) -> None:
    context = document_e2e
    reservation = _reserve(context, case=case, byte_size=declared_size)
    if len(content) == declared_size:
        _browser_put(reservation, content)
    else:
        context.api_client.put_object(
            Bucket=context.environment.staging_bucket,
            Key=staging_object_key(context.identity.organization_a, reservation.id),
            Body=content,
            ContentType="application/pdf",
        )
    _complete(context, reservation, expected_sha256=expected_sha256)
    assert _worker(context).run_once() == 0

    with context.app_runtime.transaction() as session:
        install_principal_context(session, context.identity.principal_a)
        failed = context.service.get_upload_session(
            session,
            principal=context.identity.principal_a,
            upload_id=reservation.id,
        )
    assert failed.state is UploadSessionProjectionState.FAILED
    assert failed.failure_code == failure_code
    assert context.recording_client.permanent_copy_calls == []

    with Session(context.owner_engine) as session:
        state = session.execute(
            text(
                "SELECT reservation.state, job.state, "
                "(SELECT count(*) FROM document.document_revision AS revision "
                " WHERE revision.id = upload.target_revision_id) AS revisions "
                "FROM document.upload_session AS upload "
                "JOIN platform.staging_upload_reservation AS reservation "
                "ON reservation.id = upload.id "
                "JOIN platform.knowledge_job AS job "
                "ON job.id = upload.completion_job_id "
                "WHERE upload.id = :upload_id"
            ),
            {"upload_id": reservation.id},
        ).one()
        assert tuple(state) == ("PENDING", "DEAD_LETTER", 0)
    verification = context.admin_client.list_objects_v2(
        Bucket=context.environment.staging_bucket,
        Prefix=(f"organizations/{context.identity.organization_a}/verification/{reservation.id}"),
    )
    assert verification.get("Contents", []) == []
