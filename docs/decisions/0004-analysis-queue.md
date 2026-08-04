# ADR 0004: Transactional outbox and Redis Streams

- **Status:** Accepted
- **Date:** 2026-08-03

## Context

An API request must not create a durable analysis job and then lose the message
that tells a worker to process it. PostgreSQL and Redis cannot share a normal
transaction, so writing the job and publishing directly to Redis would leave a
failure window between those operations.

RepoLume also needs multiple workers, explicit acknowledgements, and recovery
when a worker stops after claiming a request.

## Decision

Create one `analysis_requested` outbox row in the same PostgreSQL transaction
as each analysis job. A publisher leases unpublished rows with
`FOR UPDATE SKIP LOCKED`, writes versioned fields to a Redis Stream, and marks
the row published in a second short transaction.

Workers use a Redis consumer group. New deliveries are read with `XREADGROUP`,
stale pending deliveries are recovered with `XAUTOCLAIM`, and a message is
acknowledged only after processing reaches a durable outcome.

Delivery is at least once. A publisher can stop after `XADD` succeeds but before
the outbox row is marked published, so consumers must tolerate duplicates. The
existing compare-and-set lifecycle transitions provide the idempotency guard:
only the worker that still observes the expected job state may advance it.

## Consequences

- A committed job always has a retryable publication record.
- Redis outages do not require holding a database transaction open.
- Multiple publishers and workers can operate without intentionally claiming
  the same available work.
- Duplicate messages are possible and expected.
- Operations must monitor unpublished outbox rows and stale Redis pending
  entries.
- Dead-letter policy, bounded retry schedules, and full worker orchestration
  remain separate decisions.

## Alternatives considered

Publishing directly after inserting the job was rejected because a process
failure could leave a queued job that no worker can discover. Using PostgreSQL
as both database and queue was deferred because Redis Streams provides the
consumer-group behavior planned for the worker while the outbox preserves the
database reliability boundary.
