"""PostgreSQL transactional outbox repository."""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from pcbknowledge.platform.ids import new_uuid7
from pcbknowledge.platform.jobs.payload import JsonValue, payload_digest_matches
from pcbknowledge.platform.jobs.repository import TenantScope
from pcbknowledge.platform.outbox.errors import (
    OutboxIdempotencyConflictError,
    OutboxLeaseLostError,
    OutboxTransitionError,
)
from pcbknowledge.platform.outbox.models import OutboxEvent, OutboxState


class OutboxRepository:
    """Outbox operations that participate in the caller-owned transaction."""

    def add(
        self,
        session: Session,
        *,
        scope: TenantScope,
        event_type: str,
        aggregate_type: str,
        aggregate_id: UUID,
        payload: dict[str, JsonValue],
        payload_sha256: str,
        idempotency_key: str,
        max_attempts: int,
        now: datetime,
        available_at: datetime,
        schedule_explicit: bool,
    ) -> OutboxEvent:
        statement = (
            insert(OutboxEvent)
            .values(
                id=new_uuid7(),
                organization_id=scope.organization_id,
                project_id=scope.project_id,
                access_scope=scope.access_scope.value,
                event_type=event_type,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                payload=payload,
                payload_sha256=payload_sha256,
                idempotency_key=idempotency_key,
                state=OutboxState.READY.value,
                available_at=available_at,
                attempts=0,
                max_attempts=max_attempts,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing()
            .returning(OutboxEvent)
        )
        created = session.execute(statement).scalar_one_or_none()
        if created is not None:
            return created
        existing = session.scalar(
            self._scoped_events(scope).where(
                OutboxEvent.event_type == event_type,
                OutboxEvent.idempotency_key == idempotency_key,
            )
        )
        if (
            existing is None
            or existing.payload_sha256 != payload_sha256
            or existing.aggregate_type != aggregate_type
            or existing.aggregate_id != aggregate_id
            or existing.max_attempts != max_attempts
            or (
                existing.available_at != available_at
                if schedule_explicit
                else existing.available_at != existing.created_at
            )
        ):
            raise OutboxIdempotencyConflictError()
        return existing

    def recover_expired(
        self,
        session: Session,
        *,
        scope: TenantScope,
        now: datetime,
        event_types: frozenset[str] | None = None,
        limit: int = 100,
    ) -> tuple[int, int]:
        statement = (
            self._scoped_events(scope)
            .where(
                OutboxEvent.state == OutboxState.RUNNING.value,
                OutboxEvent.lease_expires_at <= now,
            )
            .order_by(OutboxEvent.lease_expires_at, OutboxEvent.created_at)
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
        if event_types is not None:
            statement = statement.where(OutboxEvent.event_type.in_(event_types))
        recovered = 0
        dead_lettered = 0
        for event in session.scalars(statement):
            event.lease_owner = None
            event.lease_expires_at = None
            event.updated_at = now
            if event.attempts >= event.max_attempts:
                event.state = OutboxState.DEAD_LETTER.value
                event.last_failure_code = "LEASE_EXPIRED_MAX_ATTEMPTS"
                dead_lettered += 1
            else:
                event.state = OutboxState.READY.value
                event.available_at = now
                event.last_failure_code = "LEASE_EXPIRED"
                recovered += 1
        session.flush()
        return recovered, dead_lettered

    def claim(
        self,
        session: Session,
        *,
        scope: TenantScope,
        worker_id: str,
        now: datetime,
        lease_duration: timedelta,
        batch_size: int,
        event_types: frozenset[str] | None = None,
    ) -> list[OutboxEvent]:
        statement = (
            self._scoped_events(scope)
            .where(
                OutboxEvent.state == OutboxState.READY.value,
                OutboxEvent.available_at <= now,
                OutboxEvent.attempts < OutboxEvent.max_attempts,
            )
            .order_by(OutboxEvent.created_at, OutboxEvent.id)
            .with_for_update(skip_locked=True)
            .limit(batch_size)
        )
        if event_types is not None:
            statement = statement.where(OutboxEvent.event_type.in_(event_types))
        events: list[OutboxEvent] = []
        for event in session.scalars(statement):
            if not payload_digest_matches(event.payload, event.payload_sha256):
                event.state = OutboxState.DEAD_LETTER.value
                event.last_failure_code = "PAYLOAD_INTEGRITY_FAILED"
                event.updated_at = now
                continue
            event.state = OutboxState.RUNNING.value
            event.lease_owner = worker_id
            event.lease_expires_at = now + lease_duration
            event.attempts += 1
            event.updated_at = now
            events.append(event)
        session.flush()
        return events

    def mark_published(
        self,
        session: Session,
        *,
        scope: TenantScope,
        event_id: UUID,
        worker_id: str,
        now: datetime,
    ) -> OutboxEvent:
        event = self.active_event(
            session,
            scope=scope,
            event_id=event_id,
            worker_id=worker_id,
            now=now,
        )
        event.state = OutboxState.PUBLISHED.value
        event.lease_owner = None
        event.lease_expires_at = None
        event.published_at = now
        event.updated_at = now
        session.flush()
        return event

    def mark_failed(
        self,
        session: Session,
        *,
        scope: TenantScope,
        event_id: UUID,
        worker_id: str,
        failure_code: str,
        now: datetime,
        retry_at: datetime | None,
    ) -> OutboxEvent:
        event = self.active_event(
            session,
            scope=scope,
            event_id=event_id,
            worker_id=worker_id,
            now=now,
        )
        event.lease_owner = None
        event.lease_expires_at = None
        event.last_failure_code = failure_code
        event.updated_at = now
        if retry_at is None or event.attempts >= event.max_attempts:
            event.state = OutboxState.DEAD_LETTER.value
        else:
            event.state = OutboxState.READY.value
            event.available_at = retry_at
        session.flush()
        return event

    def active_event(
        self,
        session: Session,
        *,
        scope: TenantScope,
        event_id: UUID,
        worker_id: str,
        now: datetime,
    ) -> OutboxEvent:
        event = session.scalar(
            self._scoped_events(scope).where(OutboxEvent.id == event_id).with_for_update()
        )
        if event is None:
            raise OutboxTransitionError()
        if (
            event.state != OutboxState.RUNNING.value
            or event.lease_owner != worker_id
            or event.lease_expires_at is None
            or event.lease_expires_at <= now
        ):
            raise OutboxLeaseLostError()
        return event

    @staticmethod
    def _scoped_events(scope: TenantScope) -> Select[tuple[OutboxEvent]]:
        return select(OutboxEvent).where(
            OutboxEvent.organization_id == scope.organization_id,
            OutboxEvent.project_id == scope.project_id,
            OutboxEvent.access_scope == scope.access_scope.value,
        )
