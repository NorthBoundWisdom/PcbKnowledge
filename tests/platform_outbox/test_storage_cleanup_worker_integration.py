"""End-to-end cleanup-worker tests against PostgreSQL and SeaweedFS.

These tests deliberately use the migration owner only for fixture setup and
verification.  Every discovery, claim, state transition, and object deletion is
performed through the real ``pcbknowledge_worker`` database and S3 identities.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Protocol, cast
from uuid import UUID

import boto3  # type: ignore[import-untyped]
import pytest
from botocore.config import Config  # type: ignore[import-untyped]
from botocore.exceptions import ClientError  # type: ignore[import-untyped]
from sqlalchemy import Engine, create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from pcbknowledge.platform.database import DatabaseRuntime
from pcbknowledge.platform.database.health import EXPECTED_DATABASE_REVISION
from pcbknowledge.platform.ids import new_uuid7
from pcbknowledge.platform.jobs import AccessScope, TenantScope
from pcbknowledge.platform.outbox import OutboxEvent, OutboxService, OutboxState
from pcbknowledge.platform.outbox.worker import WorkerOutboxDispatcher
from pcbknowledge.platform.storage import (
    ObjectAsset,
    ObjectAssetState,
    SeaweedFsS3Adapter,
    StagingUploadReservation,
    StagingUploadState,
    content_addressed_key,
    staging_object_key,
    verification_object_key,
)
from pcbknowledge.platform.storage.adapter import S3Client
from pcbknowledge.platform.time import utc_now
from tests.platform_jobs.postgres_support import (
    IdentitySeed,
    require_postgres_engine,
    reset_and_seed,
)
from tests.platform_storage.test_storage_seaweedfs import require_s3_environment

_WORKER_DATABASE_DSN_ENV = "PCBKNOWLEDGE_M1_WORKER_DATABASE_DSN"


class _AdminS3(Protocol):
    def create_bucket(self, **kwargs: object) -> object: ...

    def put_object(self, **kwargs: object) -> object: ...

    def head_object(self, **kwargs: object) -> Mapping[str, object]: ...

    def delete_object(self, **kwargs: object) -> object: ...


@dataclass(slots=True, repr=False)
class _IntegrationEnvironment:
    admin_engine: Engine
    worker_runtime: DatabaseRuntime
    admin_s3: _AdminS3
    worker_s3: S3Client
    worker_adapter: SeaweedFsS3Adapter
    bucket: str
    staging_bucket: str
    seed: IdentitySeed
    staged_keys: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class _FinalizedUpload:
    scope: TenantScope
    asset_id: UUID
    upload_id: UUID
    event_id: UUID | None
    content: bytes


@dataclass(frozen=True, slots=True)
class _PendingUpload:
    scope: TenantScope
    upload_id: UUID
    content: bytes


class _FailFirstDelete:
    """Inject one transport failure before delegating to the real worker client."""

    def __init__(self, delegate: S3Client) -> None:
        self._delegate = delegate
        self.failures = 0

    def delete_object(self, **kwargs: object) -> object:
        if self.failures == 0:
            self.failures += 1
            raise OSError("injected S3 transport failure")
        return self._delegate.delete_object(**kwargs)


@pytest.fixture
def integration_environment() -> Iterator[_IntegrationEnvironment]:
    s3_environment = require_s3_environment()
    worker_dsn = os.environ.get(_WORKER_DATABASE_DSN_ENV)
    if worker_dsn is None:
        pytest.skip(f"set {_WORKER_DATABASE_DSN_ENV} to run cleanup-worker integration tests")

    admin_engine = require_postgres_engine()
    worker_url = make_url(worker_dsn)
    if worker_url.drivername != "postgresql+psycopg" or worker_url.database is None:
        admin_engine.dispose()
        pytest.fail(f"{_WORKER_DATABASE_DSN_ENV} must be a postgresql+psycopg DSN")
    if worker_url.database != admin_engine.url.database:
        admin_engine.dispose()
        pytest.fail("worker and fixture DSNs must target the same disposable database")

    worker_engine = create_engine(worker_dsn, pool_pre_ping=True)
    try:
        with worker_engine.connect() as connection:
            session_user, current_user, revision = connection.execute(
                text(
                    "SELECT session_user, current_user, "
                    "(SELECT version_num FROM public.alembic_version)"
                )
            ).one()
            attributes = connection.execute(
                text(
                    "SELECT rolsuper, rolinherit, rolcreaterole, rolcreatedb, "
                    "rolreplication, rolbypassrls "
                    "FROM pg_catalog.pg_roles WHERE rolname = current_user"
                )
            ).one()
        if (session_user, current_user) != ("pcbknowledge_worker", "pcbknowledge_worker"):
            pytest.fail("worker DSN must log in directly as pcbknowledge_worker")
        if revision != EXPECTED_DATABASE_REVISION:
            pytest.fail(f"cleanup-worker test database must be at {EXPECTED_DATABASE_REVISION}")
        if tuple(attributes) != (False, False, False, False, False, False):
            pytest.fail("pcbknowledge_worker has unsafe PostgreSQL role attributes")

        seed = reset_and_seed(admin_engine)
        admin_s3 = cast(
            _AdminS3,
            boto3.client(
                "s3",
                endpoint_url=s3_environment.endpoint,
                aws_access_key_id=s3_environment.admin_access_key,
                aws_secret_access_key=s3_environment.admin_secret_key,
                region_name="us-east-1",
                config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
            ),
        )
        worker_s3 = cast(
            S3Client,
            boto3.client(
                "s3",
                endpoint_url=s3_environment.endpoint,
                aws_access_key_id=s3_environment.worker_access_key,
                aws_secret_access_key=s3_environment.worker_secret_key,
                region_name="us-east-1",
                config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
            ),
        )
        for bucket in (s3_environment.bucket, s3_environment.staging_bucket):
            _ensure_bucket(admin_s3, bucket)

        worker_runtime = DatabaseRuntime(
            engine=worker_engine,
            session_factory=sessionmaker(
                bind=worker_engine,
                autoflush=False,
                expire_on_commit=False,
            ),
        )
        environment = _IntegrationEnvironment(
            admin_engine=admin_engine,
            worker_runtime=worker_runtime,
            admin_s3=admin_s3,
            worker_s3=worker_s3,
            worker_adapter=SeaweedFsS3Adapter(
                internal_client=worker_s3,
                presign_client=worker_s3,
                bucket=s3_environment.bucket,
                staging_bucket=s3_environment.staging_bucket,
            ),
            bucket=s3_environment.bucket,
            staging_bucket=s3_environment.staging_bucket,
            seed=seed,
        )
        try:
            yield environment
        finally:
            for key in reversed(environment.staged_keys):
                admin_s3.delete_object(Bucket=environment.staging_bucket, Key=key)
    finally:
        worker_engine.dispose()
        admin_engine.dispose()


def test_worker_discovers_claims_deletes_and_commits_cleanup(
    integration_environment: _IntegrationEnvironment,
) -> None:
    environment = integration_environment
    upload = _seed_finalized_upload(
        environment,
        project_id=environment.seed.project_a1,
        access_scope_id=environment.seed.scope_a1,
        license_policy_id=environment.seed.policy_a1_allow,
        content=b"worker cleanup end-to-end evidence",
        add_cleanup_event=True,
        put_staging=True,
    )
    assert upload.event_id is not None
    _assert_unscoped_worker_rls_denies_all(environment)

    dispatcher = _dispatcher(environment, adapter=environment.worker_adapter)
    assert dispatcher.run_once(maximum_scopes=10, batch_size=10) == 1

    with Session(environment.admin_engine) as session:
        reservation = session.execute(
            select(
                StagingUploadReservation.state,
                StagingUploadReservation.cleaned_at,
                StagingUploadReservation.asset_id,
            ).where(StagingUploadReservation.id == upload.upload_id)
        ).one()
        event = session.execute(
            select(
                OutboxEvent.state,
                OutboxEvent.attempts,
                OutboxEvent.last_failure_code,
                OutboxEvent.published_at,
            ).where(OutboxEvent.id == upload.event_id)
        ).one()
    assert reservation.state == StagingUploadState.CLEANED.value
    assert reservation.cleaned_at is not None
    assert reservation.asset_id == upload.asset_id
    assert event.state == OutboxState.PUBLISHED.value
    assert event.attempts == 1
    assert event.last_failure_code is None
    assert event.published_at is not None
    _assert_staging_pair_missing(environment, upload.upload_id)
    _assert_unscoped_worker_rls_denies_all(environment)


def test_worker_sweeps_expired_pending_upload_without_outbox(
    integration_environment: _IntegrationEnvironment,
) -> None:
    environment = integration_environment
    upload = _seed_expired_pending_upload(
        environment,
        project_id=environment.seed.project_a1,
        access_scope_id=environment.seed.scope_a1,
        license_policy_id=environment.seed.policy_a1_allow,
        content=b"abandoned staging upload",
    )
    _assert_unscoped_worker_rls_denies_all(environment)

    dispatcher = _dispatcher(environment, adapter=environment.worker_adapter)
    assert dispatcher.run_once(maximum_scopes=10, batch_size=10) == 1

    with Session(environment.admin_engine) as session:
        reservation = session.execute(
            select(
                StagingUploadReservation.state,
                StagingUploadReservation.cleaned_at,
                StagingUploadReservation.asset_id,
            ).where(StagingUploadReservation.id == upload.upload_id)
        ).one()
        event_count = session.scalar(select(func.count()).select_from(OutboxEvent))
    assert reservation.state == StagingUploadState.EXPIRED.value
    assert reservation.cleaned_at is not None
    assert reservation.asset_id is None
    assert event_count == 0
    _assert_staging_pair_missing(environment, upload.upload_id)


def test_cross_project_upload_and_asset_bindings_never_delete_staging(
    integration_environment: _IntegrationEnvironment,
) -> None:
    environment = integration_environment
    protected = _seed_finalized_upload(
        environment,
        project_id=environment.seed.project_a1,
        access_scope_id=environment.seed.scope_a1,
        license_policy_id=environment.seed.policy_a1_allow,
        content=b"project A1 protected staging",
        add_cleanup_event=False,
        put_staging=True,
    )
    other_project = _seed_finalized_upload(
        environment,
        project_id=environment.seed.project_a2,
        access_scope_id=environment.seed.scope_a2,
        license_policy_id=environment.seed.policy_a2_allow,
        content=b"project A2 different asset",
        add_cleanup_event=False,
        put_staging=False,
    )
    wrong_scope_event = _add_cleanup_event(
        environment,
        scope=other_project.scope,
        asset_id=protected.asset_id,
        upload_id=protected.upload_id,
        idempotency_suffix="cross-project-upload",
    )
    wrong_asset_event = _add_cleanup_event(
        environment,
        scope=protected.scope,
        asset_id=other_project.asset_id,
        upload_id=protected.upload_id,
        idempotency_suffix="cross-project-asset",
    )
    _assert_unscoped_worker_rls_denies_all(environment)

    dispatcher = _dispatcher(environment, adapter=environment.worker_adapter)
    assert dispatcher.run_once(maximum_scopes=10, batch_size=10) == 0

    with Session(environment.admin_engine) as session:
        states = session.execute(
            select(
                OutboxEvent.id,
                OutboxEvent.state,
                OutboxEvent.attempts,
                OutboxEvent.last_failure_code,
            ).where(OutboxEvent.id.in_({wrong_scope_event, wrong_asset_event}))
        ).all()
        protected_state = session.execute(
            select(
                StagingUploadReservation.state,
                StagingUploadReservation.cleaned_at,
                StagingUploadReservation.asset_id,
            ).where(StagingUploadReservation.id == protected.upload_id)
        ).one()
    assert {row.id for row in states} == {wrong_scope_event, wrong_asset_event}
    assert all(row.state == OutboxState.DEAD_LETTER.value for row in states)
    assert all(row.attempts == 1 for row in states)
    assert all(row.last_failure_code == "INVALID_CLEANUP_EVENT" for row in states)
    assert protected_state.state == StagingUploadState.FINALIZED.value
    assert protected_state.cleaned_at is None
    assert protected_state.asset_id == protected.asset_id
    _assert_staging_pair_present(environment, protected.upload_id, protected.content)


def test_s3_delete_failure_is_retried_without_losing_database_binding(
    integration_environment: _IntegrationEnvironment,
) -> None:
    environment = integration_environment
    upload = _seed_finalized_upload(
        environment,
        project_id=environment.seed.project_a1,
        access_scope_id=environment.seed.scope_a1,
        license_policy_id=environment.seed.policy_a1_allow,
        content=b"retryable cleanup evidence",
        add_cleanup_event=True,
        put_staging=True,
    )
    assert upload.event_id is not None
    fail_first = _FailFirstDelete(environment.worker_s3)
    failing_adapter = SeaweedFsS3Adapter(
        internal_client=cast(S3Client, fail_first),
        presign_client=environment.worker_s3,
        bucket=environment.bucket,
        staging_bucket=environment.staging_bucket,
    )
    service = OutboxService(
        jitter=lambda _attempt: 0.5,
        base_backoff=timedelta(0),
    )
    dispatcher = _dispatcher(environment, adapter=failing_adapter, service=service)

    # Bound the first cycle to one claim so the retry is observable as a
    # separate worker cycle even though this test deliberately uses zero
    # backoff.
    assert dispatcher.run_once(maximum_scopes=10, batch_size=1) == 0
    assert fail_first.failures == 1
    with Session(environment.admin_engine) as session:
        first_event = session.execute(
            select(
                OutboxEvent.state,
                OutboxEvent.attempts,
                OutboxEvent.last_failure_code,
            ).where(OutboxEvent.id == upload.event_id)
        ).one()
        first_reservation = session.execute(
            select(
                StagingUploadReservation.state,
                StagingUploadReservation.cleaned_at,
            ).where(StagingUploadReservation.id == upload.upload_id)
        ).one()
    assert first_event.state == OutboxState.READY.value
    assert first_event.attempts == 1
    assert first_event.last_failure_code == "OBJECT_STORE_UNAVAILABLE"
    assert first_reservation.state == StagingUploadState.FINALIZED.value
    assert first_reservation.cleaned_at is None
    _assert_staging_pair_present(environment, upload.upload_id, upload.content)

    assert dispatcher.run_once(maximum_scopes=10, batch_size=10) == 1
    with Session(environment.admin_engine) as session:
        final_event = session.execute(
            select(OutboxEvent.state, OutboxEvent.attempts, OutboxEvent.published_at).where(
                OutboxEvent.id == upload.event_id
            )
        ).one()
        final_reservation = session.execute(
            select(
                StagingUploadReservation.state,
                StagingUploadReservation.cleaned_at,
            ).where(StagingUploadReservation.id == upload.upload_id)
        ).one()
    assert final_event.state == OutboxState.PUBLISHED.value
    assert final_event.attempts == 2
    assert final_event.published_at is not None
    assert final_reservation.state == StagingUploadState.CLEANED.value
    assert final_reservation.cleaned_at is not None
    _assert_staging_pair_missing(environment, upload.upload_id)


def _dispatcher(
    environment: _IntegrationEnvironment,
    *,
    adapter: SeaweedFsS3Adapter,
    service: OutboxService | None = None,
) -> WorkerOutboxDispatcher:
    return WorkerOutboxDispatcher(
        database=environment.worker_runtime,
        adapter=adapter,
        worker_id=f"integration-cleanup-{new_uuid7()}",
        service=service,
    )


def _seed_finalized_upload(
    environment: _IntegrationEnvironment,
    *,
    project_id: UUID,
    access_scope_id: UUID,
    license_policy_id: UUID,
    content: bytes,
    add_cleanup_event: bool,
    put_staging: bool,
) -> _FinalizedUpload:
    now = utc_now()
    scope = TenantScope(environment.seed.organization_a, project_id, AccessScope.PROJECT)
    digest = hashlib.sha256(content).hexdigest()
    asset_id = new_uuid7()
    upload_id = new_uuid7()
    event_id: UUID | None = None
    with Session(environment.admin_engine, expire_on_commit=False) as session, session.begin():
        session.add(
            ObjectAsset(
                id=asset_id,
                organization_id=scope.organization_id,
                project_id=scope.project_id,
                access_scope=scope.access_scope.value,
                access_scope_id=access_scope_id,
                license_policy_id=license_policy_id,
                asset_kind="ORIGINAL",
                bucket=environment.bucket,
                object_key=content_addressed_key(scope.organization_id, digest),
                sha256=digest,
                byte_size=len(content),
                media_type="application/pdf",
                state=ObjectAssetState.AVAILABLE.value,
                created_by_subject_id=environment.seed.subject_a,
                created_at=now - timedelta(minutes=4),
            )
        )
        session.flush()
        session.add(
            StagingUploadReservation(
                id=upload_id,
                organization_id=scope.organization_id,
                project_id=scope.project_id,
                access_scope=scope.access_scope.value,
                access_scope_id=access_scope_id,
                license_policy_id=license_policy_id,
                created_by_subject_id=environment.seed.subject_a,
                media_type="application/pdf",
                expected_byte_size=len(content),
                state=StagingUploadState.FINALIZED.value,
                asset_id=asset_id,
                created_at=now - timedelta(minutes=10),
                expires_at=now - timedelta(minutes=5),
                finalized_at=now - timedelta(minutes=4),
            )
        )
        session.flush()
        if add_cleanup_event:
            event = OutboxService(clock=lambda: now, jitter=lambda _attempt: 0.5).add(
                session,
                scope=scope,
                event_type="storage.staging_cleanup.requested",
                aggregate_type="object_asset",
                aggregate_id=asset_id,
                payload={"asset_id": str(asset_id), "upload_id": str(upload_id)},
                idempotency_key=f"cleanup-integration:{upload_id}",
                available_at=now - timedelta(seconds=1),
            )
            event_id = event.id
    if put_staging:
        _put_staging_pair(environment, upload_id, content)
    return _FinalizedUpload(
        scope=scope,
        asset_id=asset_id,
        upload_id=upload_id,
        event_id=event_id,
        content=content,
    )


def _seed_expired_pending_upload(
    environment: _IntegrationEnvironment,
    *,
    project_id: UUID,
    access_scope_id: UUID,
    license_policy_id: UUID,
    content: bytes,
) -> _PendingUpload:
    now = utc_now()
    scope = TenantScope(environment.seed.organization_a, project_id, AccessScope.PROJECT)
    upload_id = new_uuid7()
    with Session(environment.admin_engine) as session, session.begin():
        session.add(
            StagingUploadReservation(
                id=upload_id,
                organization_id=scope.organization_id,
                project_id=scope.project_id,
                access_scope=scope.access_scope.value,
                access_scope_id=access_scope_id,
                license_policy_id=license_policy_id,
                created_by_subject_id=environment.seed.subject_a,
                media_type="application/pdf",
                expected_byte_size=len(content),
                state=StagingUploadState.PENDING.value,
                created_at=now - timedelta(minutes=10),
                expires_at=now - timedelta(minutes=2),
            )
        )
    _put_staging_pair(environment, upload_id, content)
    return _PendingUpload(scope=scope, upload_id=upload_id, content=content)


def _add_cleanup_event(
    environment: _IntegrationEnvironment,
    *,
    scope: TenantScope,
    asset_id: UUID,
    upload_id: UUID,
    idempotency_suffix: str,
) -> UUID:
    now = utc_now()
    with Session(environment.admin_engine, expire_on_commit=False) as session, session.begin():
        event = OutboxService(clock=lambda: now, jitter=lambda _attempt: 0.5).add(
            session,
            scope=scope,
            event_type="storage.staging_cleanup.requested",
            aggregate_type="object_asset",
            aggregate_id=asset_id,
            payload={"asset_id": str(asset_id), "upload_id": str(upload_id)},
            idempotency_key=f"{idempotency_suffix}:{new_uuid7()}",
            available_at=now - timedelta(seconds=1),
        )
        return event.id


def _put_staging_pair(
    environment: _IntegrationEnvironment,
    upload_id: UUID,
    content: bytes,
) -> None:
    keys = (
        staging_object_key(environment.seed.organization_a, upload_id),
        verification_object_key(environment.seed.organization_a, upload_id),
    )
    for key in keys:
        environment.staged_keys.append(key)
        environment.admin_s3.put_object(
            Bucket=environment.staging_bucket,
            Key=key,
            Body=content,
        )


def _assert_staging_pair_present(
    environment: _IntegrationEnvironment,
    upload_id: UUID,
    content: bytes,
) -> None:
    for key in (
        staging_object_key(environment.seed.organization_a, upload_id),
        verification_object_key(environment.seed.organization_a, upload_id),
    ):
        response = environment.admin_s3.head_object(
            Bucket=environment.staging_bucket,
            Key=key,
        )
        assert response["ContentLength"] == len(content)


def _assert_staging_pair_missing(
    environment: _IntegrationEnvironment,
    upload_id: UUID,
) -> None:
    for key in (
        staging_object_key(environment.seed.organization_a, upload_id),
        verification_object_key(environment.seed.organization_a, upload_id),
    ):
        with pytest.raises(ClientError) as missing:
            environment.admin_s3.head_object(
                Bucket=environment.staging_bucket,
                Key=key,
            )
        assert missing.value.response["ResponseMetadata"]["HTTPStatusCode"] == 404


def _assert_unscoped_worker_rls_denies_all(environment: _IntegrationEnvironment) -> None:
    with environment.worker_runtime.engine.connect() as connection:
        reservations = connection.scalar(
            text("SELECT count(*) FROM platform.staging_upload_reservation")
        )
        events = connection.scalar(text("SELECT count(*) FROM platform.outbox_event"))
    assert reservations == 0
    assert events == 0


def _ensure_bucket(client: _AdminS3, bucket: str) -> None:
    try:
        client.create_bucket(Bucket=bucket)
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") not in {
            "BucketAlreadyExists",
            "BucketAlreadyOwnedByYou",
        }:
            raise
