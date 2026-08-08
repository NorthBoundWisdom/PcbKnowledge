"""Real PostgreSQL transactional and delivery tests for the outbox."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Engine, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pcbknowledge.platform.ids import new_uuid7
from pcbknowledge.platform.jobs import AccessScope, JobService, KnowledgeJob, TenantScope
from pcbknowledge.platform.jobs.payload import validate_small_metadata
from pcbknowledge.platform.outbox import (
    OutboxEvent,
    OutboxIdempotencyConflictError,
    OutboxPayloadIntegrityError,
    OutboxService,
    OutboxState,
)
from pcbknowledge.platform.time import utc_now
from tests.platform_jobs.postgres_support import (
    IdentitySeed,
    install_rls_context,
    require_postgres_engine,
    reset_and_seed,
)


class RecordingPublisher:
    def __init__(self) -> None:
        self.event_ids: list[str] = []

    def publish(self, event: OutboxEvent) -> None:
        self.event_ids.append(str(event.id))


@pytest.fixture
def database() -> Iterator[tuple[Engine, IdentitySeed]]:
    engine = require_postgres_engine()
    seed = reset_and_seed(engine)
    try:
        yield engine, seed
    finally:
        engine.dispose()


def test_outbox_joins_domain_commit_and_rollback(
    database: tuple[Engine, IdentitySeed],
) -> None:
    engine, seed = database
    scope = TenantScope(seed.organization_a, seed.project_a1, AccessScope.PROJECT)
    jobs = JobService(jitter=lambda _attempt: 0.5)
    outbox = OutboxService(jitter=lambda _attempt: 0.5)

    with Session(engine) as session:
        transaction = session.begin()
        job = jobs.enqueue(
            session,
            scope=scope,
            job_type="documents.parse",
            payload={"document_revision_id": str(seed.project_a1)},
            idempotency_key="rollback-domain",
        )
        outbox.add(
            session,
            scope=scope,
            event_type="document.parse_requested",
            aggregate_type="knowledge_job",
            aggregate_id=job.id,
            payload={"job_id": str(job.id)},
            idempotency_key="rollback-event",
        )
        transaction.rollback()

    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(OutboxEvent)) == 0
        assert session.scalar(select(func.count()).select_from(KnowledgeJob)) == 0

    with Session(engine) as session, session.begin():
        job = jobs.enqueue(
            session,
            scope=scope,
            job_type="documents.parse",
            payload={"document_revision_id": str(seed.project_a1)},
            idempotency_key="commit-domain",
        )
        event = outbox.add(
            session,
            scope=scope,
            event_type="document.parse_requested",
            aggregate_type="knowledge_job",
            aggregate_id=job.id,
            payload={"job_id": str(job.id)},
            idempotency_key="commit-event",
        )
        with pytest.raises(OutboxIdempotencyConflictError):
            outbox.add(
                session,
                scope=scope,
                event_type="document.parse_requested",
                aggregate_type="knowledge_job",
                aggregate_id=seed.project_a2,
                payload={"job_id": str(job.id)},
                idempotency_key="commit-event",
            )
        event_id = event.id

    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(OutboxEvent)) == 1
        assert session.get(OutboxEvent, event_id) is not None


def test_claim_publish_and_retry_are_explicit(database: tuple[Engine, IdentitySeed]) -> None:
    engine, seed = database
    scope = TenantScope(seed.organization_a, seed.project_a1, AccessScope.PROJECT)
    now = datetime(2026, 8, 8, 12, tzinfo=UTC)
    service = OutboxService(
        clock=lambda: now,
        jitter=lambda _attempt: 0.5,
        lease_duration=timedelta(seconds=30),
    )
    with Session(engine) as session, session.begin():
        first = service.add(
            session,
            scope=scope,
            event_type="search.reindex_requested",
            aggregate_type="document_revision",
            aggregate_id=seed.project_a1,
            payload={"document_revision_id": str(seed.project_a1)},
            idempotency_key="publish-event",
        )
        second = service.add(
            session,
            scope=scope,
            event_type="search.reindex_requested",
            aggregate_type="document_revision",
            aggregate_id=seed.project_a2,
            payload={"document_revision_id": str(seed.project_a2)},
            idempotency_key="retry-event",
            max_attempts=3,
        )
        first_id = first.id
        second_id = second.id

    with Session(engine) as session, session.begin():
        claimed = service.claim(
            session,
            scope=scope,
            worker_id="outbox-worker",
            batch_size=2,
        )
        assert {event.id for event in claimed} == {first_id, second_id}

    publisher = RecordingPublisher()
    with Session(engine) as session, session.begin():
        published = service.publish(
            session,
            scope=scope,
            event_id=first_id,
            worker_id="outbox-worker",
            publisher=publisher,
        )
        retried = service.fail(
            session,
            scope=scope,
            event_id=second_id,
            worker_id="outbox-worker",
            failure_code="DESTINATION_UNAVAILABLE",
        )
        assert published.state == OutboxState.PUBLISHED.value
        assert retried.state == OutboxState.READY.value
        assert retried.available_at == now + timedelta(seconds=5)

    assert publisher.event_ids == [str(first_id)]


def test_outbox_schedule_is_idempotent_and_past_deadlines_are_ready(
    database: tuple[Engine, IdentitySeed],
) -> None:
    engine, seed = database
    scope = TenantScope(seed.organization_a, seed.project_a1, AccessScope.PROJECT)
    now = datetime(2026, 8, 8, 12, tzinfo=UTC)
    service = OutboxService(clock=lambda: now)
    future = now + timedelta(minutes=5)

    with Session(engine) as session, session.begin():
        scheduled = service.add(
            session,
            scope=scope,
            event_type="storage.cleanup",
            aggregate_type="object_asset",
            aggregate_id=seed.project_a1,
            payload={"asset_id": str(seed.project_a1)},
            idempotency_key="scheduled-cleanup",
            available_at=future,
        )
        duplicate = service.add(
            session,
            scope=scope,
            event_type="storage.cleanup",
            aggregate_type="object_asset",
            aggregate_id=seed.project_a1,
            payload={"asset_id": str(seed.project_a1)},
            idempotency_key="scheduled-cleanup",
            available_at=future,
        )
        assert duplicate.id == scheduled.id
        with pytest.raises(OutboxIdempotencyConflictError):
            service.add(
                session,
                scope=scope,
                event_type="storage.cleanup",
                aggregate_type="object_asset",
                aggregate_id=seed.project_a1,
                payload={"asset_id": str(seed.project_a1)},
                idempotency_key="scheduled-cleanup",
                available_at=future + timedelta(minutes=1),
            )

        past = service.add(
            session,
            scope=scope,
            event_type="storage.cleanup",
            aggregate_type="object_asset",
            aggregate_id=seed.project_a2,
            payload={"asset_id": str(seed.project_a2)},
            idempotency_key="expired-cleanup",
            available_at=now - timedelta(minutes=1),
        )
        assert past.available_at == now


def test_outbox_insert_and_identity_are_guarded_in_postgresql(
    database: tuple[Engine, IdentitySeed],
) -> None:
    engine, seed = database
    scope = TenantScope(seed.organization_a, seed.project_a1, AccessScope.PROJECT)
    now = utc_now()
    service = OutboxService(clock=lambda: now)
    with Session(engine) as session, session.begin():
        install_rls_context(
            session,
            organization_id=seed.organization_a,
            project_ids=frozenset({seed.project_a1}),
        )
        event = service.add(
            session,
            scope=scope,
            event_type="integrity.immutable",
            aggregate_type="document_revision",
            aggregate_id=seed.project_a1,
            payload={"document_revision_id": str(seed.project_a1)},
            idempotency_key="immutable-outbox",
        )
        event_id = event.id

    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            savepoint = connection.begin_nested()
            try:
                with pytest.raises(DBAPIError):
                    connection.execute(
                        text(
                            "UPDATE platform.outbox_event "
                            "SET aggregate_id = :aggregate_id WHERE id = :event_id"
                        ),
                        {"aggregate_id": seed.project_a2, "event_id": event_id},
                    )
            finally:
                savepoint.rollback()

            connection.execute(text("SET LOCAL ROLE pcbknowledge_app"))
            connection.execute(
                text("SELECT set_config('pcbknowledge.organization_id', :value, true)"),
                {"value": str(seed.organization_a)},
            )
            connection.execute(
                text("SELECT set_config('pcbknowledge.project_ids', :value, true)"),
                {"value": str(seed.project_a1)},
            )
            _empty_payload, empty_digest = validate_small_metadata({})
            savepoint = connection.begin_nested()
            try:
                with pytest.raises(DBAPIError):
                    connection.execute(
                        text(
                            "INSERT INTO platform.outbox_event ("
                            "id, organization_id, project_id, access_scope, event_type, "
                            "aggregate_type, aggregate_id, payload, payload_sha256, "
                            "idempotency_key, state, available_at, attempts, max_attempts, "
                            "created_at, updated_at"
                            ") VALUES ("
                            ":id, :organization_id, :project_id, 'PROJECT', "
                            "'integrity.forged_running', 'document_revision', :aggregate_id, "
                            "'{}'::jsonb, :digest, 'forged-running', 'RUNNING', :now, "
                            "0, 5, :now, :now)"
                        ),
                        {
                            "id": new_uuid7(),
                            "organization_id": seed.organization_a,
                            "project_id": seed.project_a1,
                            "aggregate_id": seed.project_a1,
                            "digest": empty_digest,
                            "now": now,
                        },
                    )
            finally:
                savepoint.rollback()
        finally:
            transaction.rollback()

    with engine.connect() as connection:
        assert not connection.scalar(
            text(
                "SELECT has_column_privilege("
                "'pcbknowledge_app', 'platform.outbox_event', 'payload', 'UPDATE')"
            )
        )
        assert not connection.scalar(
            text(
                "SELECT has_column_privilege("
                "'pcbknowledge_app', 'platform.outbox_event', 'lease_owner', 'INSERT')"
            )
        )


def test_outbox_payload_integrity_is_checked_at_claim_and_before_publish(
    database: tuple[Engine, IdentitySeed],
) -> None:
    engine, seed = database
    scope = TenantScope(seed.organization_a, seed.project_a1, AccessScope.PROJECT)
    now = utc_now()
    service = OutboxService(
        clock=lambda: now,
        jitter=lambda _attempt: 0.5,
        lease_duration=timedelta(minutes=5),
    )
    corrupt_ready_id = new_uuid7()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO platform.outbox_event ("
                "id, organization_id, project_id, access_scope, event_type, "
                "aggregate_type, aggregate_id, payload, payload_sha256, "
                "idempotency_key, state, available_at, attempts, max_attempts, "
                "created_at, updated_at"
                ") VALUES ("
                ":id, :organization_id, :project_id, 'PROJECT', "
                "'integrity.corrupt_ready', 'document_revision', :aggregate_id, "
                "CAST(:corrupt_payload AS jsonb), :wrong_digest, "
                "'corrupt-ready', 'READY', :now, 0, 5, :now, :now)"
            ),
            {
                "id": corrupt_ready_id,
                "organization_id": seed.organization_a,
                "project_id": seed.project_a1,
                "aggregate_id": seed.project_a1,
                "corrupt_payload": '{"page":1}',
                "wrong_digest": "0" * 64,
                "now": now,
            },
        )

    with Session(engine) as session, session.begin():
        install_rls_context(
            session,
            organization_id=seed.organization_a,
            project_ids=frozenset({seed.project_a1}),
        )
        assert service.claim(session, scope=scope, worker_id="integrity-worker") == []
    with Session(engine) as session:
        corrupt = session.get(OutboxEvent, corrupt_ready_id)
        assert corrupt is not None
        assert corrupt.state == OutboxState.DEAD_LETTER.value
        assert corrupt.last_failure_code == "PAYLOAD_INTEGRITY_FAILED"

    with Session(engine) as session, session.begin():
        install_rls_context(
            session,
            organization_id=seed.organization_a,
            project_ids=frozenset({seed.project_a1}),
        )
        valid = service.add(
            session,
            scope=scope,
            event_type="integrity.pre_publish",
            aggregate_type="document_revision",
            aggregate_id=seed.project_a1,
            payload={"document_revision_id": str(seed.project_a1)},
            idempotency_key="integrity-pre-publish",
        )
        claimed = service.claim(session, scope=scope, worker_id="integrity-worker")
        assert [item.id for item in claimed] == [valid.id]
        valid_id = valid.id

    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE platform.outbox_event "
                "DISABLE TRIGGER enforce_outbox_event_immutable_fields"
            )
        )
        connection.execute(
            text(
                "UPDATE platform.outbox_event "
                'SET payload = \'{"document_revision_id":"tampered"}\'::jsonb '
                "WHERE id = :event_id"
            ),
            {"event_id": valid_id},
        )
        connection.execute(
            text(
                "ALTER TABLE platform.outbox_event "
                "ENABLE TRIGGER enforce_outbox_event_immutable_fields"
            )
        )

    publisher = RecordingPublisher()
    with Session(engine) as session, session.begin():
        install_rls_context(
            session,
            organization_id=seed.organization_a,
            project_ids=frozenset({seed.project_a1}),
        )
        with pytest.raises(OutboxPayloadIntegrityError):
            service.publish(
                session,
                scope=scope,
                event_id=valid_id,
                worker_id="integrity-worker",
                publisher=publisher,
            )
        failed = service.fail(
            session,
            scope=scope,
            event_id=valid_id,
            worker_id="integrity-worker",
            failure_code="PAYLOAD_INTEGRITY_FAILED",
            retryable=False,
        )
        assert failed.state == OutboxState.DEAD_LETTER.value
    assert publisher.event_ids == []
