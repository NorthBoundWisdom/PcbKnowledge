"""Real PostgreSQL tests for object registry, policy, audit, outbox, and RLS."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator, Mapping
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from pcbknowledge.platform.audit import AuditEvent, AuditWriter
from pcbknowledge.platform.jobs import AccessScope, TenantScope
from pcbknowledge.platform.outbox import OutboxEvent, OutboxService
from pcbknowledge.platform.storage import (
    AuditWriterAssetReadAuditor,
    ObjectAccessDeniedError,
    ObjectAsset,
    ObjectAuditRequiredError,
    ObjectStorageService,
    PolicyStorageAuthorizer,
    SeaweedFsS3Adapter,
    StorageRequestContext,
    staging_object_key,
)
from pcbknowledge.platform.storage.adapter import S3Client, StagingCleanupIntent
from tests.platform_jobs.postgres_support import (
    IdentitySeed,
    install_rls_context,
    require_postgres_engine,
    reset_and_seed,
)


class _Body:
    def __init__(self, content: bytes) -> None:
        self._content = content
        self._offset = 0

    def read(self, amount: int | None = None) -> bytes:
        if amount is None:
            amount = len(self._content)
        start = self._offset
        self._offset += amount
        return self._content[start : self._offset]

    def close(self) -> None:
        return None


class _MemoryS3:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.deleted: list[str] = []
        self.presigned_gets = 0

    def generate_presigned_url(
        self,
        ClientMethod: str,
        Params: Mapping[str, object],
        ExpiresIn: int,
        HttpMethod: str | None = None,
    ) -> str:
        del ExpiresIn, HttpMethod
        if ClientMethod == "get_object":
            self.presigned_gets += 1
        return f"https://objects.invalid/{ClientMethod}/{Params['Bucket']}"

    def get_object(self, **kwargs: object) -> Mapping[str, object]:
        key = cast(str, kwargs["Key"])
        content = self.objects[key]
        return {
            "Body": _Body(content),
            "ETag": hashlib.sha256(content).hexdigest(),
        }

    def copy_object(self, **kwargs: object) -> object:
        key = cast(str, kwargs["Key"])
        source = cast(dict[str, str], kwargs["CopySource"])
        source_content = self.objects[source["Key"]]
        self.objects[key] = source_content
        return {}

    def delete_object(self, **kwargs: object) -> object:
        key = cast(str, kwargs["Key"])
        self.deleted.append(key)
        self.objects.pop(key, None)
        return {}


class _FailingAuditor:
    def record_asset_read(
        self,
        session: Session,
        *,
        organization_id: UUID,
        project_id: UUID | None,
        actor_subject_id: UUID,
        asset_id: UUID,
    ) -> UUID:
        del session, organization_id, project_id, actor_subject_id, asset_id
        raise RuntimeError("deliberate safe audit failure")


@pytest.fixture
def database() -> Iterator[tuple[Engine, IdentitySeed]]:
    engine = require_postgres_engine()
    seed = reset_and_seed(engine)
    try:
        yield engine, seed
    finally:
        engine.dispose()


def _context(seed: IdentitySeed) -> StorageRequestContext:
    return StorageRequestContext(
        organization_id=seed.organization_a,
        project_ids=frozenset({seed.project_a1, seed.project_a2}),
        actor_subject_id=seed.subject_a,
    )


def _adapter(memory: _MemoryS3) -> SeaweedFsS3Adapter:
    return SeaweedFsS3Adapter(
        internal_client=cast(S3Client, memory),
        presign_client=cast(S3Client, memory),
        bucket="pcbknowledge-m1-test",
        staging_bucket="pcbknowledge-m1-test-staging",
        allow_content_write=True,
    )


def _service(seed: IdentitySeed, memory: _MemoryS3) -> ObjectStorageService:
    return ObjectStorageService(
        adapter=_adapter(memory),
        authorizer=PolicyStorageAuthorizer(seed.principal_a),
        auditor=AuditWriterAssetReadAuditor(AuditWriter(), seed.principal_a),
        outbox=OutboxService(jitter=lambda _attempt: 0.5),
    )


def _put_staging(
    memory: _MemoryS3,
    *,
    organization_id: UUID,
    upload_id: UUID,
    content: bytes,
) -> str:
    memory.objects[staging_object_key(organization_id, upload_id)] = content
    return hashlib.sha256(content).hexdigest()


def _reserve_and_put(
    session: Session,
    *,
    service: ObjectStorageService,
    seed: IdentitySeed,
    memory: _MemoryS3,
    scope: TenantScope,
    access_scope_id: UUID,
    license_policy_id: UUID,
    content: bytes,
) -> tuple[UUID, str]:
    upload = service.create_staging_upload(
        session,
        context=_context(seed),
        scope=scope,
        access_scope_id=access_scope_id,
        license_policy_id=license_policy_id,
        media_type="application/pdf",
        expected_byte_size=len(content),
    )
    digest = _put_staging(
        memory,
        organization_id=scope.organization_id,
        upload_id=upload.upload_id,
        content=content,
    )
    return upload.upload_id, digest


def test_finalize_rollback_is_retryable_and_cleanup_is_after_commit(
    database: tuple[Engine, IdentitySeed],
) -> None:
    engine, seed = database
    memory = _MemoryS3()
    service = _service(seed, memory)
    scope = TenantScope(seed.organization_a, seed.project_a1, AccessScope.PROJECT)
    content = b"transactional evidence"
    with Session(engine) as session, session.begin():
        install_rls_context(
            session,
            organization_id=seed.organization_a,
            project_ids=_context(seed).project_ids,
        )
        upload_id, digest = _reserve_and_put(
            session,
            service=service,
            seed=seed,
            memory=memory,
            scope=scope,
            access_scope_id=seed.scope_a1,
            license_policy_id=seed.policy_a1_allow,
            content=content,
        )
    staging_key = staging_object_key(seed.organization_a, upload_id)

    with Session(engine) as session:
        transaction = session.begin()
        install_rls_context(
            session,
            organization_id=seed.organization_a,
            project_ids=_context(seed).project_ids,
        )
        service.finalize_staging(
            session,
            context=_context(seed),
            scope=scope,
            upload_id=upload_id,
            expected_sha256=digest,
            media_type="application/pdf",
            asset_kind="ORIGINAL",
            access_scope_id=seed.scope_a1,
            license_policy_id=seed.policy_a1_allow,
        )
        assert staging_key in memory.objects
        assert session.scalar(select(func.count()).select_from(OutboxEvent)) == 1
        transaction.rollback()

    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(ObjectAsset)) == 0
        assert session.scalar(select(func.count()).select_from(OutboxEvent)) == 0
    assert staging_key in memory.objects

    with Session(engine) as session, session.begin():
        install_rls_context(
            session,
            organization_id=seed.organization_a,
            project_ids=_context(seed).project_ids,
        )
        asset = service.finalize_staging(
            session,
            context=_context(seed),
            scope=scope,
            upload_id=upload_id,
            expected_sha256=digest,
            media_type="application/pdf",
            asset_kind="ORIGINAL",
            access_scope_id=seed.scope_a1,
            license_policy_id=seed.policy_a1_allow,
        )
        asset_id = asset.id

    with Session(engine) as session:
        assert session.get(ObjectAsset, asset_id) is not None
        assert session.scalar(select(func.count()).select_from(OutboxEvent)) == 1
    assert staging_key in memory.objects

    # An outbox consumer is the only component allowed to remove staging.
    _adapter(memory).cleanup_staging(
        StagingCleanupIntent(organization_id=seed.organization_a, upload_id=upload_id)
    )
    assert staging_key not in memory.objects


def test_same_content_has_distinct_project_assets_and_rls_visibility(
    database: tuple[Engine, IdentitySeed],
) -> None:
    engine, seed = database
    memory = _MemoryS3()
    service = _service(seed, memory)
    content = b"one physical object, two logical grants"
    digest = hashlib.sha256(content).hexdigest()
    inputs = (
        (seed.project_a1, seed.scope_a1, seed.policy_a1_allow),
        (seed.project_a2, seed.scope_a2, seed.policy_a2_allow),
    )
    asset_ids: list[UUID] = []
    object_keys: list[str] = []
    with Session(engine) as session, session.begin():
        install_rls_context(
            session,
            organization_id=seed.organization_a,
            project_ids=_context(seed).project_ids,
        )
        for project_id, access_scope_id, license_policy_id in inputs:
            item_scope = TenantScope(seed.organization_a, project_id, AccessScope.PROJECT)
            upload_id, _ = _reserve_and_put(
                session,
                service=service,
                seed=seed,
                memory=memory,
                scope=item_scope,
                access_scope_id=access_scope_id,
                license_policy_id=license_policy_id,
                content=content,
            )
            asset = service.finalize_staging(
                session,
                context=_context(seed),
                scope=item_scope,
                upload_id=upload_id,
                expected_sha256=digest,
                media_type="application/pdf",
                asset_kind="ORIGINAL",
                access_scope_id=access_scope_id,
                license_policy_id=license_policy_id,
            )
            asset_ids.append(asset.id)
            object_keys.append(asset.object_key)

    assert len(set(asset_ids)) == 2
    assert len(set(object_keys)) == 1
    with Session(engine) as session, session.begin():
        install_rls_context(
            session,
            organization_id=seed.organization_a,
            project_ids=frozenset({seed.project_a1}),
        )
        visible = list(session.scalars(select(ObjectAsset)))
        assert [asset.project_id for asset in visible] == [seed.project_a1]


def test_download_requires_policy_and_durable_audit_before_presign(
    database: tuple[Engine, IdentitySeed],
) -> None:
    engine, seed = database
    memory = _MemoryS3()
    service = _service(seed, memory)
    scope = TenantScope(seed.organization_a, seed.project_a1, AccessScope.PROJECT)
    asset_ids: list[UUID] = []
    with Session(engine) as session, session.begin():
        install_rls_context(
            session,
            organization_id=seed.organization_a,
            project_ids=_context(seed).project_ids,
        )
        for content, asset_kind, policy_id in (
            (b"allowed evidence", "ORIGINAL", seed.policy_a1_allow),
            (b"denied evidence", "LICENSE_BLOCKED", seed.policy_a1_deny),
        ):
            upload_id, digest = _reserve_and_put(
                session,
                service=service,
                seed=seed,
                memory=memory,
                scope=scope,
                access_scope_id=seed.scope_a1,
                license_policy_id=policy_id,
                content=content,
            )
            asset = service.finalize_staging(
                session,
                context=_context(seed),
                scope=scope,
                upload_id=upload_id,
                expected_sha256=digest,
                media_type="application/pdf",
                asset_kind=asset_kind,
                access_scope_id=seed.scope_a1,
                license_policy_id=policy_id,
            )
            asset_ids.append(asset.id)

    with Session(engine) as session, session.begin():
        install_rls_context(
            session,
            organization_id=seed.organization_a,
            project_ids=_context(seed).project_ids,
        )
        download = service.create_download(
            session,
            context=_context(seed),
            asset_id=asset_ids[0],
        )
        assert download.url.startswith("https://objects.invalid/get_object/")
        assert memory.presigned_gets == 1
        assert session.get(AuditEvent, download.audit_event_id) is not None

    with Session(engine) as session, session.begin():
        install_rls_context(
            session,
            organization_id=seed.organization_a,
            project_ids=_context(seed).project_ids,
        )
        with pytest.raises(ObjectAccessDeniedError):
            service.create_download(
                session,
                context=_context(seed),
                asset_id=asset_ids[1],
            )
        assert memory.presigned_gets == 1

    failing_service = ObjectStorageService(
        adapter=_adapter(memory),
        authorizer=PolicyStorageAuthorizer(seed.principal_a),
        auditor=_FailingAuditor(),
        outbox=OutboxService(jitter=lambda _attempt: 0.5),
    )
    with Session(engine) as session, session.begin():
        install_rls_context(
            session,
            organization_id=seed.organization_a,
            project_ids=_context(seed).project_ids,
        )
        with pytest.raises(ObjectAuditRequiredError):
            failing_service.create_download(
                session,
                context=_context(seed),
                asset_id=asset_ids[0],
            )
        assert memory.presigned_gets == 1

    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(AuditEvent)) == 1
