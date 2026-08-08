# ADR-008: Use a PostgreSQL job queue

## Status

Accepted — 2026-08-08.

## Context

Parsing, thumbnails, indexing, and evaluation are asynchronous, but their enqueueing must be atomic with domain changes. P0 throughput does not justify another durable system.

## Decision

Store jobs in PostgreSQL. Workers claim bounded batches with `FOR UPDATE SKIP LOCKED`, leases, heartbeats, idempotency keys, retry policy, and dead-letter state. Transactional outbox rows coordinate external side effects.

## Alternatives

- Celery plus Redis/RabbitMQ.
- Kafka.
- In-process background tasks.
- Temporal or Camunda.

## Consequences

Enqueue and business state share a transaction and recovery story. Polling and lease logic must be carefully tested, and high queue volume can contend with transactional traffic.

## Rollback

Introduce a broker/workflow engine only after measured queue pressure or workflow complexity crosses the documented trigger. Keep idempotency and outbox handoff until replay and reconciliation are proven.
