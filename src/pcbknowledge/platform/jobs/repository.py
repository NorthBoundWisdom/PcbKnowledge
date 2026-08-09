"""Transactional repository for PostgreSQL job leasing and effect receipts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import ColumnElement, Select, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from pcbknowledge.platform.ids import new_uuid7
from pcbknowledge.platform.jobs.errors import (
    InvalidJobTransitionError,
    JobEffectProvenanceUnknownError,
    JobIdempotencyConflictError,
    JobLeaseLostError,
    JobNotFoundError,
    JobPayloadIntegrityError,
)
from pcbknowledge.platform.jobs.models import (
    AccessScope,
    JobEffectReceipt,
    JobState,
    KnowledgeJob,
)
from pcbknowledge.platform.jobs.payload import JsonValue, payload_digest_matches


@dataclass(frozen=True, slots=True)
class TenantScope:
    organization_id: UUID
    project_id: UUID | None
    access_scope: AccessScope

    def __post_init__(self) -> None:
        if (self.access_scope is AccessScope.ORGANIZATION) != (self.project_id is None):
            raise ValueError("access scope and project must agree")


class JobRepository:
    """Repository methods never commit; the caller owns one explicit transaction."""

    def enqueue(
        self,
        session: Session,
        *,
        scope: TenantScope,
        job_type: str,
        payload: dict[str, JsonValue],
        payload_sha256: str,
        idempotency_key: str,
        priority: int,
        max_attempts: int,
        available_at: datetime,
        schedule_explicit: bool,
        now: datetime,
    ) -> KnowledgeJob:
        job_id = new_uuid7()
        statement = (
            insert(KnowledgeJob)
            .values(
                id=job_id,
                organization_id=scope.organization_id,
                project_id=scope.project_id,
                access_scope=scope.access_scope.value,
                job_type=job_type,
                payload=payload,
                payload_sha256=payload_sha256,
                idempotency_key=idempotency_key,
                priority=priority,
                state=JobState.READY.value,
                available_at=available_at,
                attempts=0,
                max_attempts=max_attempts,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing()
            .returning(KnowledgeJob)
        )
        created = session.execute(statement).scalar_one_or_none()
        if created is not None:
            return created

        existing = session.scalar(
            self._scoped_jobs(scope).where(
                KnowledgeJob.job_type == job_type,
                KnowledgeJob.idempotency_key == idempotency_key,
            )
        )
        if existing is None:
            raise JobIdempotencyConflictError()
        if (
            existing.payload_sha256 != payload_sha256
            or existing.priority != priority
            or existing.max_attempts != max_attempts
            or (
                existing.available_at != available_at
                if schedule_explicit
                else existing.available_at != existing.created_at
            )
        ):
            raise JobIdempotencyConflictError()
        return existing

    def recover_expired_leases(
        self,
        session: Session,
        *,
        scope: TenantScope,
        now: datetime,
        limit: int = 100,
    ) -> tuple[int, int]:
        statement = (
            self._scoped_jobs(scope)
            .where(
                KnowledgeJob.state == JobState.RUNNING.value,
                KnowledgeJob.lease_expires_at <= now,
            )
            .order_by(KnowledgeJob.lease_expires_at, KnowledgeJob.created_at)
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
        recovered = 0
        dead_lettered = 0
        for job in session.scalars(statement):
            job.lease_owner = None
            job.lease_expires_at = None
            job.updated_at = now
            if job.attempts >= job.max_attempts:
                job.state = JobState.DEAD_LETTER.value
                job.last_failure_code = "LEASE_EXPIRED_MAX_ATTEMPTS"
                dead_lettered += 1
            else:
                job.state = JobState.READY.value
                job.available_at = now
                job.last_failure_code = "LEASE_EXPIRED"
                recovered += 1
        session.flush()
        return recovered, dead_lettered

    def claim_ready(
        self,
        session: Session,
        *,
        scope: TenantScope,
        worker_id: str,
        now: datetime,
        lease_duration: timedelta,
        batch_size: int,
        job_types: frozenset[str] | None = None,
    ) -> list[KnowledgeJob]:
        statement = (
            self._scoped_jobs(scope)
            .where(
                KnowledgeJob.state == JobState.READY.value,
                KnowledgeJob.available_at <= now,
                KnowledgeJob.attempts < KnowledgeJob.max_attempts,
            )
            .order_by(KnowledgeJob.priority.desc(), KnowledgeJob.created_at, KnowledgeJob.id)
            .with_for_update(skip_locked=True)
            .limit(batch_size)
        )
        if job_types is not None:
            statement = statement.where(KnowledgeJob.job_type.in_(job_types))
        jobs: list[KnowledgeJob] = []
        for job in session.scalars(statement):
            if not payload_digest_matches(job.payload, job.payload_sha256):
                job.state = JobState.DEAD_LETTER.value
                job.last_failure_code = "PAYLOAD_INTEGRITY_FAILED"
                job.updated_at = now
                continue
            job.state = JobState.RUNNING.value
            job.lease_owner = worker_id
            job.lease_expires_at = now + lease_duration
            job.attempts += 1
            job.updated_at = now
            jobs.append(job)
        session.flush()
        return jobs

    def renew_lease(
        self,
        session: Session,
        *,
        scope: TenantScope,
        job_id: UUID,
        worker_id: str,
        now: datetime,
        lease_duration: timedelta,
    ) -> KnowledgeJob:
        job = self._locked_job(session, scope=scope, job_id=job_id)
        self._require_active_lease(job, worker_id=worker_id, now=now)
        job.lease_expires_at = now + lease_duration
        job.updated_at = now
        session.flush()
        return job

    def complete(
        self,
        session: Session,
        *,
        scope: TenantScope,
        job_id: UUID,
        worker_id: str,
        now: datetime,
    ) -> KnowledgeJob:
        job = self._locked_job(session, scope=scope, job_id=job_id)
        self._require_active_lease(job, worker_id=worker_id, now=now)
        self._require_payload_integrity(job)
        job.state = JobState.COMPLETED.value
        job.lease_owner = None
        job.lease_expires_at = None
        job.completed_at = now
        job.updated_at = now
        session.flush()
        return job

    def fail(
        self,
        session: Session,
        *,
        scope: TenantScope,
        job_id: UUID,
        worker_id: str,
        now: datetime,
        failure_code: str,
        retry_at: datetime | None,
    ) -> KnowledgeJob:
        job = self._locked_job(session, scope=scope, job_id=job_id)
        self._require_active_lease(job, worker_id=worker_id, now=now)
        job.lease_owner = None
        job.lease_expires_at = None
        job.last_failure_code = failure_code
        job.updated_at = now
        if retry_at is None or job.attempts >= job.max_attempts:
            job.state = JobState.DEAD_LETTER.value
        else:
            job.state = JobState.READY.value
            job.available_at = retry_at
        session.flush()
        return job

    def cancel(
        self,
        session: Session,
        *,
        scope: TenantScope,
        job_id: UUID,
        now: datetime,
    ) -> KnowledgeJob:
        job = self._locked_job(session, scope=scope, job_id=job_id)
        if job.state in {JobState.COMPLETED.value, JobState.CANCELLED.value}:
            raise InvalidJobTransitionError()
        job.state = JobState.CANCELLED.value
        job.lease_owner = None
        job.lease_expires_at = None
        job.cancelled_at = now
        job.updated_at = now
        session.flush()
        return job

    def manual_retry(
        self,
        session: Session,
        *,
        scope: TenantScope,
        job_id: UUID,
        now: datetime,
    ) -> KnowledgeJob:
        job = self._locked_job(session, scope=scope, job_id=job_id)
        if job.state != JobState.DEAD_LETTER.value:
            raise InvalidJobTransitionError()
        job.state = JobState.READY.value
        job.attempts = 0
        job.available_at = now
        job.last_failure_code = None
        job.updated_at = now
        session.flush()
        return job

    def record_effect_once(
        self,
        session: Session,
        *,
        scope: TenantScope,
        job_id: UUID,
        effect_name: str,
        effect_sha256: str,
        worker_id: str,
        lease_attempt: int,
        now: datetime,
    ) -> bool:
        job = self._locked_job(session, scope=scope, job_id=job_id)
        self._require_active_lease(job, worker_id=worker_id, now=now)
        if job.attempts != lease_attempt:
            raise JobLeaseLostError()
        self._require_payload_integrity(job)
        receipt_id = new_uuid7()
        statement = (
            insert(JobEffectReceipt)
            .values(
                id=receipt_id,
                job_id=job.id,
                organization_id=scope.organization_id,
                project_id=scope.project_id,
                access_scope=scope.access_scope.value,
                effect_name=effect_name,
                effect_sha256=effect_sha256,
                lease_attempt=lease_attempt,
                lease_owner=worker_id,
                recorded_at=now,
            )
            .on_conflict_do_nothing()
            .returning(JobEffectReceipt.id)
        )
        inserted = session.scalar(statement)
        if inserted is not None:
            return True
        existing = session.scalar(
            select(JobEffectReceipt).where(
                JobEffectReceipt.job_id == job.id,
                JobEffectReceipt.effect_name == effect_name,
            )
        )
        if existing is None or existing.effect_sha256 != effect_sha256:
            raise JobIdempotencyConflictError()
        if existing.lease_attempt is None or existing.lease_owner is None:
            raise JobEffectProvenanceUnknownError()
        return False

    @staticmethod
    def _scope_conditions(scope: TenantScope) -> tuple[ColumnElement[bool], ...]:
        return (
            KnowledgeJob.organization_id == scope.organization_id,
            KnowledgeJob.project_id == scope.project_id,
            KnowledgeJob.access_scope == scope.access_scope.value,
        )

    def _scoped_jobs(self, scope: TenantScope) -> Select[tuple[KnowledgeJob]]:
        return select(KnowledgeJob).where(*self._scope_conditions(scope))

    def _locked_job(self, session: Session, *, scope: TenantScope, job_id: UUID) -> KnowledgeJob:
        job = session.scalar(
            self._scoped_jobs(scope).where(KnowledgeJob.id == job_id).with_for_update()
        )
        if job is None:
            raise JobNotFoundError()
        return job

    @staticmethod
    def _require_active_lease(job: KnowledgeJob, *, worker_id: str, now: datetime) -> None:
        if (
            job.state != JobState.RUNNING.value
            or job.lease_owner != worker_id
            or job.lease_expires_at is None
            or job.lease_expires_at <= now
        ):
            raise JobLeaseLostError()

    @staticmethod
    def _require_payload_integrity(job: KnowledgeJob) -> None:
        if not payload_digest_matches(job.payload, job.payload_sha256):
            raise JobPayloadIntegrityError()
