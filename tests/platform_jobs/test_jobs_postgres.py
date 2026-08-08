"""Real PostgreSQL lease, idempotency, and RLS integration tests."""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import Engine, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pcbknowledge.platform.ids import new_uuid7
from pcbknowledge.platform.jobs import (
    AccessScope,
    JobEffectProvenanceUnknownError,
    JobEffectReceipt,
    JobIdempotencyConflictError,
    JobLeaseLostError,
    JobPayloadIntegrityError,
    JobService,
    JobState,
    KnowledgeJob,
    TenantScope,
)
from pcbknowledge.platform.jobs.payload import JsonValue, validate_small_metadata
from pcbknowledge.platform.outbox import OutboxEvent, OutboxService
from pcbknowledge.platform.time import utc_now
from tests.platform_jobs.postgres_support import (
    IdentitySeed,
    install_rls_context,
    require_postgres_engine,
    reset_and_seed,
)


@dataclass(slots=True)
class MutableClock:
    value: datetime

    def __call__(self) -> datetime:
        return self.value


@pytest.fixture
def database() -> Iterator[tuple[Engine, IdentitySeed]]:
    engine = require_postgres_engine()
    seed = reset_and_seed(engine)
    try:
        yield engine, seed
    finally:
        engine.dispose()


def test_idempotency_effect_receipt_and_dead_letter_recovery(
    database: tuple[Engine, IdentitySeed],
) -> None:
    engine, seed = database
    scope = TenantScope(seed.organization_a, seed.project_a1, AccessScope.PROJECT)
    effect_scope = TenantScope(seed.organization_a, seed.project_a2, AccessScope.PROJECT)
    clock = MutableClock(utc_now())
    service = JobService(
        clock=clock,
        jitter=lambda _attempt: 0.5,
        lease_duration=timedelta(seconds=30),
    )
    outbox = OutboxService(clock=clock, jitter=lambda _attempt: 0.5)

    with Session(engine) as session, session.begin():
        first = service.enqueue(
            session,
            scope=scope,
            job_type="documents.parse",
            payload={"document_revision_id": str(seed.project_a1)},
            idempotency_key="parse-revision-1",
            max_attempts=2,
        )
        duplicate = service.enqueue(
            session,
            scope=scope,
            job_type="documents.parse",
            payload={"document_revision_id": str(seed.project_a1)},
            idempotency_key="parse-revision-1",
            max_attempts=2,
        )
        assert first.id == duplicate.id
        with pytest.raises(JobIdempotencyConflictError):
            service.enqueue(
                session,
                scope=scope,
                job_type="documents.parse",
                payload={"document_revision_id": str(seed.project_a2)},
                idempotency_key="parse-revision-1",
            )
        effect_job = service.enqueue(
            session,
            scope=effect_scope,
            job_type="documents.index",
            payload={"document_revision_id": str(seed.project_a2)},
            idempotency_key="index-revision-2",
        )
        effect_digest = hashlib.sha256(b"parsed-document:revision-1").hexdigest()
        with pytest.raises(JobLeaseLostError):
            service.record_effect_once(
                session,
                scope=effect_scope,
                job_id=effect_job.id,
                effect_name="parsed_document.created",
                effect_sha256=effect_digest,
                worker_id="worker-effect",
                lease_attempt=1,
            )
        job_id = first.id
        effect_job_id = effect_job.id

    with Session(engine) as session, session.begin():
        effect_claim = service.claim(
            session,
            scope=effect_scope,
            worker_id="worker-effect",
        )
        assert [job.id for job in effect_claim] == [effect_job_id]
        if service.record_effect_once(
            session,
            scope=effect_scope,
            job_id=effect_job_id,
            effect_name="parsed_document.created",
            effect_sha256=effect_digest,
            worker_id="worker-effect",
            lease_attempt=effect_claim[0].attempts,
        ):
            outbox.add(
                session,
                scope=effect_scope,
                event_type="parsed_document.created",
                aggregate_type="knowledge_job",
                aggregate_id=effect_job_id,
                payload={"job_id": str(effect_job_id)},
                idempotency_key="parsed-document-effect-1",
            )
        assert not service.record_effect_once(
            session,
            scope=effect_scope,
            job_id=effect_job_id,
            effect_name="parsed_document.created",
            effect_sha256=effect_digest,
            worker_id="worker-effect",
            lease_attempt=effect_claim[0].attempts,
        )
        receipt = session.scalar(
            select(JobEffectReceipt).where(JobEffectReceipt.job_id == effect_job_id)
        )
        assert receipt is not None
        assert receipt.lease_attempt == effect_claim[0].attempts
        assert receipt.lease_owner == "worker-effect"
        assert receipt.recorded_at <= utc_now()
        service.complete(
            session,
            scope=effect_scope,
            job_id=effect_job_id,
            worker_id="worker-effect",
        )
        assert session.scalar(select(func.count()).select_from(OutboxEvent)) == 1

    with Session(engine) as session, session.begin():
        claimed = service.claim(session, scope=scope, worker_id="worker-a")
        assert [job.id for job in claimed] == [job_id]
        assert claimed[0].attempts == 1

    clock.value += timedelta(seconds=31)
    with Session(engine) as session, session.begin():
        reclaimed = service.claim(session, scope=scope, worker_id="worker-b")
        assert [job.id for job in reclaimed] == [job_id]
        assert reclaimed[0].attempts == 2
        failed = service.fail(
            session,
            scope=scope,
            job_id=job_id,
            worker_id="worker-b",
            failure_code="PARSER_FAILED",
        )
        assert failed.state == JobState.DEAD_LETTER.value
        retried = service.manual_retry(session, scope=scope, job_id=job_id)
        assert retried.state == JobState.READY.value
        assert retried.attempts == 0


def test_skip_locked_claims_are_disjoint_and_priority_ordered(
    database: tuple[Engine, IdentitySeed],
) -> None:
    engine, seed = database
    scope = TenantScope(seed.organization_a, seed.project_a1, AccessScope.PROJECT)
    now = datetime(2026, 8, 8, 12, tzinfo=UTC)
    service = JobService(clock=lambda: now, jitter=lambda _attempt: 0.5)
    with Session(engine) as session, session.begin():
        high_priority_id: UUID | None = None
        for index in range(12):
            job = service.enqueue(
                session,
                scope=scope,
                job_type="documents.parse",
                payload={"document_revision_id": str(index)},
                idempotency_key=f"concurrent-{index}",
                priority=100 if index == 11 else 0,
            )
            if index == 11:
                high_priority_id = job.id
    assert high_priority_id is not None

    barrier = threading.Barrier(2)

    def claim(worker_id: str) -> set[UUID]:
        with Session(engine) as session, session.begin():
            install_rls_context(
                session,
                organization_id=seed.organization_a,
                project_ids=frozenset({seed.project_a1}),
            )
            barrier.wait(timeout=10)
            return {
                job.id
                for job in service.claim(
                    session,
                    scope=scope,
                    worker_id=worker_id,
                    batch_size=5,
                )
            }

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(claim, "worker-1")
        second_future = executor.submit(claim, "worker-2")
        first = first_future.result(timeout=20)
        second = second_future.result(timeout=20)

    assert first.isdisjoint(second)
    assert len(first | second) == 10
    assert high_priority_id in first | second

    with Session(engine) as session:
        remaining = list(session.scalars(select(KnowledgeJob).where(KnowledgeJob.state == "READY")))
        assert len(remaining) == 2
    assert {job.priority for job in remaining} == {0}


def test_schedule_is_timezone_safe_and_part_of_idempotency(
    database: tuple[Engine, IdentitySeed],
) -> None:
    engine, seed = database
    scope = TenantScope(seed.organization_a, seed.project_a1, AccessScope.PROJECT)
    clock = MutableClock(datetime(2026, 8, 8, 12, tzinfo=UTC))
    service = JobService(clock=clock)
    first_schedule = clock.value + timedelta(minutes=5)

    with Session(engine) as session, session.begin():
        first = service.enqueue(
            session,
            scope=scope,
            job_type="documents.scheduled_parse",
            payload={"document_revision_id": str(seed.project_a1)},
            idempotency_key="scheduled-parse",
            available_at=first_schedule,
        )
        duplicate = service.enqueue(
            session,
            scope=scope,
            job_type="documents.scheduled_parse",
            payload={"document_revision_id": str(seed.project_a1)},
            idempotency_key="scheduled-parse",
            available_at=first_schedule,
        )
        assert duplicate.id == first.id
        with pytest.raises(JobIdempotencyConflictError):
            service.enqueue(
                session,
                scope=scope,
                job_type="documents.scheduled_parse",
                payload={"document_revision_id": str(seed.project_a1)},
                idempotency_key="scheduled-parse",
                available_at=first_schedule + timedelta(minutes=1),
            )
        with pytest.raises(JobIdempotencyConflictError):
            service.enqueue(
                session,
                scope=scope,
                job_type="documents.scheduled_parse",
                payload={"document_revision_id": str(seed.project_a1)},
                idempotency_key="scheduled-parse",
            )

        immediate = service.enqueue(
            session,
            scope=scope,
            job_type="documents.immediate_parse",
            payload={"document_revision_id": str(seed.project_a2)},
            idempotency_key="immediate-parse",
        )
        clock.value += timedelta(seconds=1)
        immediate_duplicate = service.enqueue(
            session,
            scope=scope,
            job_type="documents.immediate_parse",
            payload={"document_revision_id": str(seed.project_a2)},
            idempotency_key="immediate-parse",
        )
        assert immediate_duplicate.id == immediate.id


def test_rls_blocks_untrusted_scope_expansion(database: tuple[Engine, IdentitySeed]) -> None:
    engine, seed = database
    service = JobService(jitter=lambda _attempt: 0.5)
    scopes = [
        TenantScope(seed.organization_a, None, AccessScope.ORGANIZATION),
        TenantScope(seed.organization_a, seed.project_a1, AccessScope.PROJECT),
        TenantScope(seed.organization_a, seed.project_a2, AccessScope.PROJECT),
        TenantScope(seed.organization_b, seed.project_b1, AccessScope.PROJECT),
    ]
    with Session(engine) as session, session.begin():
        for index, scope in enumerate(scopes):
            service.enqueue(
                session,
                scope=scope,
                job_type="rls.probe",
                payload={"index": index},
                idempotency_key=f"rls-{index}",
            )

    with Session(engine) as session, session.begin():
        install_rls_context(
            session,
            organization_id=seed.organization_a,
            project_ids=frozenset({seed.project_a1}),
        )
        visible = list(session.scalars(select(KnowledgeJob).order_by(KnowledgeJob.id)))
        assert {job.project_id for job in visible} == {None, seed.project_a1}
        hidden_claim = service.claim(
            session,
            scope=TenantScope(seed.organization_a, seed.project_a2, AccessScope.PROJECT),
            worker_id="scope-expansion-attempt",
        )
        assert hidden_claim == []

    with pytest.raises(DBAPIError), Session(engine) as session, session.begin():
        install_rls_context(
            session,
            organization_id=seed.organization_a,
            project_ids=frozenset({seed.project_a1}),
        )
        service.enqueue(
            session,
            scope=TenantScope(seed.organization_b, seed.project_b1, AccessScope.PROJECT),
            job_type="rls.probe",
            payload={"index": 99},
            idempotency_key="cross-organization-denied",
        )


def test_integer_metadata_round_trips_through_jsonb_and_claim(
    database: tuple[Engine, IdentitySeed],
) -> None:
    engine, seed = database
    scope = TenantScope(seed.organization_a, seed.project_a1, AccessScope.PROJECT)
    now = utc_now()
    service = JobService(clock=lambda: now, jitter=lambda _attempt: 0.5)
    payload: dict[str, JsonValue] = {
        "page": 2,
        "metadata": {"retry": False, "offset": -4},
    }

    with Session(engine) as session, session.begin():
        install_rls_context(
            session,
            organization_id=seed.organization_a,
            project_ids=frozenset({seed.project_a1}),
        )
        job = service.enqueue(
            session,
            scope=scope,
            job_type="metadata.integer_roundtrip",
            payload=payload,
            idempotency_key="integer-roundtrip",
        )
        job_id = job.id

    with Session(engine) as session, session.begin():
        install_rls_context(
            session,
            organization_id=seed.organization_a,
            project_ids=frozenset({seed.project_a1}),
        )
        claimed = service.claim(session, scope=scope, worker_id="integer-worker")
        assert [item.id for item in claimed] == [job_id]
        assert claimed[0].payload == payload


def test_job_insert_and_identity_are_guarded_in_postgresql(
    database: tuple[Engine, IdentitySeed],
) -> None:
    engine, seed = database
    scope = TenantScope(seed.organization_a, seed.project_a1, AccessScope.PROJECT)
    now = utc_now()
    service = JobService(clock=lambda: now)
    with Session(engine) as session, session.begin():
        install_rls_context(
            session,
            organization_id=seed.organization_a,
            project_ids=frozenset({seed.project_a1}),
        )
        job = service.enqueue(
            session,
            scope=scope,
            job_type="integrity.immutable",
            payload={"document_revision_id": str(seed.project_a1)},
            idempotency_key="immutable-job",
        )
        job_id = job.id

    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            savepoint = connection.begin_nested()
            try:
                with pytest.raises(DBAPIError):
                    connection.execute(
                        text(
                            "UPDATE platform.knowledge_job "
                            'SET payload = \'{"document_revision_id":"tampered"}\'::jsonb '
                            "WHERE id = :job_id"
                        ),
                        {"job_id": job_id},
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
                            "INSERT INTO platform.knowledge_job ("
                            "id, organization_id, project_id, access_scope, job_type, "
                            "payload, payload_sha256, idempotency_key, priority, state, "
                            "available_at, attempts, max_attempts, created_at, updated_at"
                            ") VALUES ("
                            ":id, :organization_id, :project_id, 'PROJECT', "
                            "'integrity.forged_running', '{}'::jsonb, :digest, "
                            "'forged-running', 0, 'RUNNING', :now, 0, 5, :now, :now)"
                        ),
                        {
                            "id": new_uuid7(),
                            "organization_id": seed.organization_a,
                            "project_id": seed.project_a1,
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
                "'pcbknowledge_app', 'platform.knowledge_job', 'payload', 'UPDATE')"
            )
        )
        assert not connection.scalar(
            text(
                "SELECT has_column_privilege("
                "'pcbknowledge_app', 'platform.knowledge_job', 'lease_owner', 'INSERT')"
            )
        )


def test_job_payload_corruption_is_dead_lettered_and_blocks_effects(
    database: tuple[Engine, IdentitySeed],
) -> None:
    engine, seed = database
    scope = TenantScope(seed.organization_a, seed.project_a1, AccessScope.PROJECT)
    now = utc_now()
    service = JobService(
        clock=lambda: now,
        jitter=lambda _attempt: 0.5,
        lease_duration=timedelta(minutes=5),
    )

    corrupt_ready_id = new_uuid7()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO platform.knowledge_job ("
                "id, organization_id, project_id, access_scope, job_type, payload, "
                "payload_sha256, idempotency_key, priority, state, available_at, "
                "attempts, max_attempts, created_at, updated_at"
                ") VALUES ("
                ":id, :organization_id, :project_id, 'PROJECT', "
                "'integrity.corrupt_ready', CAST(:corrupt_payload AS jsonb), "
                ":wrong_digest, "
                "'corrupt-ready', 0, 'READY', :now, 0, 5, :now, :now)"
            ),
            {
                "corrupt_payload": '{"page":1}',
                "id": corrupt_ready_id,
                "organization_id": seed.organization_a,
                "project_id": seed.project_a1,
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
        corrupt = session.get(KnowledgeJob, corrupt_ready_id)
        assert corrupt is not None
        assert corrupt.state == JobState.DEAD_LETTER.value
        assert corrupt.last_failure_code == "PAYLOAD_INTEGRITY_FAILED"

    with Session(engine) as session, session.begin():
        install_rls_context(
            session,
            organization_id=seed.organization_a,
            project_ids=frozenset({seed.project_a1}),
        )
        valid = service.enqueue(
            session,
            scope=scope,
            job_type="integrity.recheck",
            payload={"document_revision_id": str(seed.project_a1)},
            idempotency_key="integrity-recheck",
        )
        valid_id = valid.id
        claimed = service.claim(session, scope=scope, worker_id="integrity-worker")
        assert [item.id for item in claimed] == [valid_id]
        lease_attempt = claimed[0].attempts

    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE platform.knowledge_job "
                "DISABLE TRIGGER enforce_knowledge_job_immutable_fields"
            )
        )
        connection.execute(
            text(
                "UPDATE platform.knowledge_job "
                'SET payload = \'{"document_revision_id":"tampered"}\'::jsonb '
                "WHERE id = :job_id"
            ),
            {"job_id": valid_id},
        )
        connection.execute(
            text(
                "ALTER TABLE platform.knowledge_job "
                "ENABLE TRIGGER enforce_knowledge_job_immutable_fields"
            )
        )

    effect_digest = hashlib.sha256(b"must-not-run").hexdigest()
    with Session(engine) as session, session.begin():
        install_rls_context(
            session,
            organization_id=seed.organization_a,
            project_ids=frozenset({seed.project_a1}),
        )
        with pytest.raises(JobPayloadIntegrityError):
            service.record_effect_once(
                session,
                scope=scope,
                job_id=valid_id,
                effect_name="integrity.effect",
                effect_sha256=effect_digest,
                worker_id="integrity-worker",
                lease_attempt=lease_attempt,
            )
        with pytest.raises(JobPayloadIntegrityError):
            service.complete(
                session,
                scope=scope,
                job_id=valid_id,
                worker_id="integrity-worker",
            )
        assert session.scalar(select(func.count()).select_from(JobEffectReceipt)) == 0


def test_unknown_legacy_effect_receipt_never_suppresses_an_effect(
    database: tuple[Engine, IdentitySeed],
) -> None:
    engine, seed = database
    scope = TenantScope(seed.organization_a, seed.project_a1, AccessScope.PROJECT)
    now = utc_now()
    service = JobService(clock=lambda: now, lease_duration=timedelta(minutes=5))
    effect_digest = hashlib.sha256(b"legacy-unknown-effect").hexdigest()
    with Session(engine) as session, session.begin():
        install_rls_context(
            session,
            organization_id=seed.organization_a,
            project_ids=frozenset({seed.project_a1}),
        )
        job = service.enqueue(
            session,
            scope=scope,
            job_type="integrity.legacy_receipt",
            payload={"document_revision_id": str(seed.project_a1)},
            idempotency_key="legacy-unknown-receipt",
        )
        claimed = service.claim(session, scope=scope, worker_id="legacy-worker")
        assert [item.id for item in claimed] == [job.id]
        job_id = job.id
        lease_attempt = claimed[0].attempts

    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE platform.job_effect_receipt "
                "DISABLE TRIGGER enforce_job_effect_receipt_insert"
            )
        )
        connection.execute(
            text(
                "INSERT INTO platform.job_effect_receipt ("
                "id, job_id, organization_id, project_id, access_scope, "
                "effect_name, effect_sha256, lease_attempt, lease_owner, recorded_at"
                ") VALUES ("
                ":id, :job_id, :organization_id, :project_id, 'PROJECT', "
                "'integrity.legacy_effect', :digest, NULL, NULL, :now)"
            ),
            {
                "id": new_uuid7(),
                "job_id": job_id,
                "organization_id": seed.organization_a,
                "project_id": seed.project_a1,
                "digest": effect_digest,
                "now": now,
            },
        )
        connection.execute(
            text(
                "ALTER TABLE platform.job_effect_receipt "
                "ENABLE TRIGGER enforce_job_effect_receipt_insert"
            )
        )

    with Session(engine) as session, session.begin():
        install_rls_context(
            session,
            organization_id=seed.organization_a,
            project_ids=frozenset({seed.project_a1}),
        )
        with pytest.raises(JobEffectProvenanceUnknownError):
            service.record_effect_once(
                session,
                scope=scope,
                job_id=job_id,
                effect_name="integrity.legacy_effect",
                effect_sha256=effect_digest,
                worker_id="legacy-worker",
                lease_attempt=lease_attempt,
            )
        receipt = session.scalar(select(JobEffectReceipt).where(JobEffectReceipt.job_id == job_id))
        assert receipt is not None
        assert receipt.lease_attempt is None
        assert receipt.lease_owner is None
