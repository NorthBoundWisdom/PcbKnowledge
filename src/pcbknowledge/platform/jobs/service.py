"""Application service for durable job scheduling and worker transitions."""

from __future__ import annotations

import random
import re
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from pcbknowledge.platform.jobs.errors import InvalidJobTransitionError
from pcbknowledge.platform.jobs.models import KnowledgeJob
from pcbknowledge.platform.jobs.payload import JsonValue, validate_sha256, validate_small_metadata
from pcbknowledge.platform.jobs.repository import JobRepository, TenantScope
from pcbknowledge.platform.time import utc_now

Clock = Callable[[], datetime]
Jitter = Callable[[int], float]

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}$")
_FAILURE_CODE = re.compile(r"^[A-Z0-9][A-Z0-9_.-]{0,127}$")


class JobService:
    """Coordinates policy while leaving commit/rollback to the request or worker."""

    def __init__(
        self,
        repository: JobRepository | None = None,
        *,
        clock: Clock = utc_now,
        jitter: Jitter | None = None,
        lease_duration: timedelta = timedelta(minutes=5),
        base_backoff: timedelta = timedelta(seconds=5),
        max_backoff: timedelta = timedelta(hours=1),
        jitter_fraction: float = 0.2,
    ) -> None:
        if lease_duration <= timedelta(0) or base_backoff <= timedelta(0):
            raise ValueError("lease and backoff durations must be positive")
        if not 0 <= jitter_fraction <= 0.5:
            raise ValueError("jitter fraction must be between zero and one half")
        self._repository = repository or JobRepository()
        self._clock = clock
        self._jitter = jitter or (lambda _attempt: random.SystemRandom().random())
        self._lease_duration = lease_duration
        self._base_backoff = base_backoff
        self._max_backoff = max_backoff
        self._jitter_fraction = jitter_fraction

    def enqueue(
        self,
        session: Session,
        *,
        scope: TenantScope,
        job_type: str,
        payload: Mapping[str, JsonValue],
        idempotency_key: str,
        priority: int = 0,
        max_attempts: int = 5,
        available_at: datetime | None = None,
    ) -> KnowledgeJob:
        self._require_identifier(job_type)
        self._require_identifier(idempotency_key)
        if not -1000 <= priority <= 1000 or not 1 <= max_attempts <= 100:
            raise InvalidJobTransitionError()
        normalized, payload_sha256 = validate_small_metadata(payload)
        now = self._now()
        scheduled_at = available_at or now
        if scheduled_at.tzinfo is None or scheduled_at.utcoffset() is None:
            raise InvalidJobTransitionError()
        if scheduled_at < now:
            raise InvalidJobTransitionError()
        return self._repository.enqueue(
            session,
            scope=scope,
            job_type=job_type,
            payload=normalized,
            payload_sha256=payload_sha256,
            idempotency_key=idempotency_key,
            priority=priority,
            max_attempts=max_attempts,
            available_at=scheduled_at,
            schedule_explicit=available_at is not None,
            now=now,
        )

    def claim(
        self,
        session: Session,
        *,
        scope: TenantScope,
        worker_id: str,
        batch_size: int = 1,
        job_types: frozenset[str] | None = None,
    ) -> list[KnowledgeJob]:
        self._require_identifier(worker_id)
        if not 1 <= batch_size <= 100:
            raise ValueError("batch size must be between 1 and 100")
        if job_types is not None:
            if not job_types:
                raise ValueError("job type filter cannot be empty")
            for job_type in job_types:
                self._require_identifier(job_type)
        now = self._now()
        self._repository.recover_expired_leases(session, scope=scope, now=now)
        return self._repository.claim_ready(
            session,
            scope=scope,
            worker_id=worker_id,
            now=now,
            lease_duration=self._lease_duration,
            batch_size=batch_size,
            job_types=job_types,
        )

    def renew_lease(
        self,
        session: Session,
        *,
        scope: TenantScope,
        job_id: UUID,
        worker_id: str,
    ) -> KnowledgeJob:
        self._require_identifier(worker_id)
        return self._repository.renew_lease(
            session,
            scope=scope,
            job_id=job_id,
            worker_id=worker_id,
            now=self._now(),
            lease_duration=self._lease_duration,
        )

    def complete(
        self,
        session: Session,
        *,
        scope: TenantScope,
        job_id: UUID,
        worker_id: str,
    ) -> KnowledgeJob:
        self._require_identifier(worker_id)
        return self._repository.complete(
            session,
            scope=scope,
            job_id=job_id,
            worker_id=worker_id,
            now=self._now(),
        )

    def fail(
        self,
        session: Session,
        *,
        scope: TenantScope,
        job_id: UUID,
        worker_id: str,
        failure_code: str,
        retryable: bool = True,
    ) -> KnowledgeJob:
        self._require_identifier(worker_id)
        if _FAILURE_CODE.fullmatch(failure_code) is None:
            raise InvalidJobTransitionError()
        now = self._now()
        job = self._repository._locked_job(session, scope=scope, job_id=job_id)
        self._repository._require_active_lease(job, worker_id=worker_id, now=now)
        retry_at = None
        if retryable and job.attempts < job.max_attempts:
            retry_at = now + self.retry_delay(job.attempts)
        return self._repository.fail(
            session,
            scope=scope,
            job_id=job_id,
            worker_id=worker_id,
            now=now,
            failure_code=failure_code,
            retry_at=retry_at,
        )

    def cancel(self, session: Session, *, scope: TenantScope, job_id: UUID) -> KnowledgeJob:
        return self._repository.cancel(session, scope=scope, job_id=job_id, now=self._now())

    def manual_retry(self, session: Session, *, scope: TenantScope, job_id: UUID) -> KnowledgeJob:
        return self._repository.manual_retry(session, scope=scope, job_id=job_id, now=self._now())

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
    ) -> bool:
        """Insert the effect receipt in the same transaction as the domain effect.

        ``True`` grants the caller the one transactional effect slot. ``False``
        means an identical receipt already exists and the effect must not run.
        """

        self._require_identifier(effect_name)
        self._require_identifier(worker_id)
        if lease_attempt < 1:
            raise InvalidJobTransitionError()
        validate_sha256(effect_sha256)
        return self._repository.record_effect_once(
            session,
            scope=scope,
            job_id=job_id,
            effect_name=effect_name,
            effect_sha256=effect_sha256,
            worker_id=worker_id,
            lease_attempt=lease_attempt,
            now=self._now(),
        )

    def retry_delay(self, attempt: int) -> timedelta:
        if attempt < 1:
            raise ValueError("attempt must be positive")
        raw_seconds = min(
            self._base_backoff.total_seconds() * (2 ** (attempt - 1)),
            self._max_backoff.total_seconds(),
        )
        sample = self._jitter(attempt)
        if not 0 <= sample <= 1:
            raise ValueError("jitter sample must be between zero and one")
        factor = 1 + self._jitter_fraction * ((2 * sample) - 1)
        return timedelta(seconds=raw_seconds * factor)

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("clock must return a timezone-aware datetime")
        return value

    @staticmethod
    def _require_identifier(value: str) -> None:
        if _IDENTIFIER.fullmatch(value) is None:
            raise InvalidJobTransitionError()
