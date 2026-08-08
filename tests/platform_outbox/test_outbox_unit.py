"""Deterministic outbox retry policy tests."""

from datetime import UTC, datetime, timedelta

from pcbknowledge.platform.outbox import OutboxService


def test_outbox_backoff_is_injectable_and_capped() -> None:
    now = datetime(2026, 8, 8, tzinfo=UTC)
    service = OutboxService(
        clock=lambda: now,
        jitter=lambda _attempt: 0.5,
        base_backoff=timedelta(seconds=3),
        max_backoff=timedelta(seconds=12),
    )

    assert service.retry_delay(1) == timedelta(seconds=3)
    assert service.retry_delay(2) == timedelta(seconds=6)
    assert service.retry_delay(3) == timedelta(seconds=12)
    assert service.retry_delay(8) == timedelta(seconds=12)
