"""Transactional outbox application service with explicit publisher injection."""

from __future__ import annotations

import random
import re
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from pcbknowledge.platform.jobs.payload import (
    JsonValue,
    payload_digest_matches,
    validate_small_metadata,
)
from pcbknowledge.platform.jobs.repository import TenantScope
from pcbknowledge.platform.outbox.errors import (
    OutboxPayloadIntegrityError,
    OutboxTransitionError,
)
from pcbknowledge.platform.outbox.models import OutboxEvent
from pcbknowledge.platform.outbox.repository import OutboxRepository
from pcbknowledge.platform.time import utc_now

Clock = Callable[[], datetime]
Jitter = Callable[[int], float]

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}$")
_FAILURE_CODE = re.compile(r"^[A-Z0-9][A-Z0-9_.-]{0,127}$")


class OutboxPublisher(Protocol):
    """External transport supplied by deployment code; no broker is implied."""

    def publish(self, event: OutboxEvent) -> None:
        """Publish at least once or raise without including credentials in the error."""


class OutboxService:
    """Writes events transactionally and dispatches claimed rows at least once."""

    def __init__(
        self,
        repository: OutboxRepository | None = None,
        *,
        clock: Clock = utc_now,
        jitter: Jitter | None = None,
        lease_duration: timedelta = timedelta(minutes=2),
        base_backoff: timedelta = timedelta(seconds=5),
        max_backoff: timedelta = timedelta(minutes=30),
        jitter_fraction: float = 0.2,
    ) -> None:
        self._repository = repository or OutboxRepository()
        self._clock = clock
        self._jitter = jitter or (lambda _attempt: random.SystemRandom().random())
        self._lease_duration = lease_duration
        self._base_backoff = base_backoff
        self._max_backoff = max_backoff
        self._jitter_fraction = jitter_fraction

    def add(
        self,
        session: Session,
        *,
        scope: TenantScope,
        event_type: str,
        aggregate_type: str,
        aggregate_id: UUID,
        payload: Mapping[str, JsonValue],
        idempotency_key: str,
        max_attempts: int = 10,
        available_at: datetime | None = None,
    ) -> OutboxEvent:
        self._require_identifier(event_type)
        self._require_identifier(aggregate_type)
        self._require_identifier(idempotency_key)
        if not 1 <= max_attempts <= 100:
            raise OutboxTransitionError()
        normalized, payload_sha256 = validate_small_metadata(payload)
        now = self._now()
        if available_at is not None and (
            available_at.tzinfo is None or available_at.utcoffset() is None
        ):
            raise OutboxTransitionError()
        if available_at is None or available_at <= now:
            schedule_explicit = False
            scheduled_at = now
        else:
            schedule_explicit = True
            scheduled_at = available_at
        return self._repository.add(
            session,
            scope=scope,
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=normalized,
            payload_sha256=payload_sha256,
            idempotency_key=idempotency_key,
            max_attempts=max_attempts,
            now=now,
            available_at=scheduled_at,
            schedule_explicit=schedule_explicit,
        )

    def claim(
        self,
        session: Session,
        *,
        scope: TenantScope,
        worker_id: str,
        batch_size: int = 10,
        event_types: frozenset[str] | None = None,
    ) -> list[OutboxEvent]:
        self._require_identifier(worker_id)
        if not 1 <= batch_size <= 100:
            raise ValueError("batch size must be between 1 and 100")
        if event_types is not None:
            if not event_types:
                raise ValueError("event_types must not be empty")
            for event_type in event_types:
                self._require_identifier(event_type)
        now = self._now()
        self._repository.recover_expired(
            session,
            scope=scope,
            now=now,
            event_types=event_types,
        )
        return self._repository.claim(
            session,
            scope=scope,
            worker_id=worker_id,
            now=now,
            lease_duration=self._lease_duration,
            batch_size=batch_size,
            event_types=event_types,
        )

    def publish(
        self,
        session: Session,
        *,
        scope: TenantScope,
        event_id: UUID,
        worker_id: str,
        publisher: OutboxPublisher,
    ) -> OutboxEvent:
        """Publish then mark delivered.

        Delivery is intentionally at-least-once: a process crash after external
        publish but before database commit causes retry with the same idempotency
        key. Consumers must deduplicate that key.
        """

        self._require_identifier(worker_id)
        now = self._now()
        event = self._repository.active_event(
            session,
            scope=scope,
            event_id=event_id,
            worker_id=worker_id,
            now=now,
        )
        if not payload_digest_matches(event.payload, event.payload_sha256):
            raise OutboxPayloadIntegrityError()
        publisher.publish(event)
        return self._repository.mark_published(
            session,
            scope=scope,
            event_id=event_id,
            worker_id=worker_id,
            now=now,
        )

    def fail(
        self,
        session: Session,
        *,
        scope: TenantScope,
        event_id: UUID,
        worker_id: str,
        failure_code: str,
        retryable: bool = True,
    ) -> OutboxEvent:
        self._require_identifier(worker_id)
        if _FAILURE_CODE.fullmatch(failure_code) is None:
            raise OutboxTransitionError()
        now = self._now()
        event = self._repository.active_event(
            session,
            scope=scope,
            event_id=event_id,
            worker_id=worker_id,
            now=now,
        )
        retry_at = None
        if retryable and event.attempts < event.max_attempts:
            retry_at = now + self.retry_delay(event.attempts)
        return self._repository.mark_failed(
            session,
            scope=scope,
            event_id=event_id,
            worker_id=worker_id,
            failure_code=failure_code,
            now=now,
            retry_at=retry_at,
        )

    def retry_delay(self, attempt: int) -> timedelta:
        if attempt < 1:
            raise ValueError("attempt must be positive")
        seconds = min(
            self._base_backoff.total_seconds() * (2 ** (attempt - 1)),
            self._max_backoff.total_seconds(),
        )
        sample = self._jitter(attempt)
        if not 0 <= sample <= 1:
            raise ValueError("jitter sample must be between zero and one")
        return timedelta(seconds=seconds * (1 + self._jitter_fraction * ((2 * sample) - 1)))

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("clock must return a timezone-aware datetime")
        return value

    @staticmethod
    def _require_identifier(value: str) -> None:
        if _IDENTIFIER.fullmatch(value) is None:
            raise OutboxTransitionError()
