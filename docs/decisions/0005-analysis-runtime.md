# ADR 0005: Opt-in API runtime and bounded worker execution

- **Status:** Accepted
- **Date:** 2026-08-03

## Context

Checkpoint 13 made job creation and queue publication reliable, but the HTTP
job-service interface, publisher process, worker pipeline, and result storage
were still isolated. Connecting them must preserve three invariants:

1. the API never performs repository analysis inside a request;
2. a worker never acknowledges a message before its durable outcome is stored;
3. duplicate delivery never runs a completed or already-active job twice.

The API and worker remain independently deployable applications. They need to
coordinate through PostgreSQL and Redis without importing one application as a
runtime dependency of the other.

## Decision

The API installs its durable job service and background outbox publisher only
when `REPOLUME_ANALYSIS_RUNTIME_ENABLED=true`. FastAPI lifespan owns the
publisher thread and its database and Redis resources. Without the flag, the
existing safe `503` behavior remains.

The worker owns a small persistence adapter for the shared analysis tables.
The table contract remains migration-owned by the API; the worker never creates
or migrates production schema. Pipeline lifecycle callbacks persist `cloning`
and `analyzing` before expensive work proceeds. Completion stores the graph and
terminal state atomically, and failures store only the pipeline's safe code and
message.

The worker command processes at most one recovered or new delivery with
`--once`. This gives tests and future process supervision a bounded operation.
A continuously running service is intentionally deferred.

## Delivery behavior

- A terminal job makes a repeated message a harmless acknowledged duplicate.
- A new duplicate for an active job is acknowledged without rerunning analysis.
- A stale reclaimed message for an active job marks that attempt failed with a
  safe `analysis_abandoned` reason.
- Missing jobs and malformed messages are acknowledged as discarded poison
  deliveries.
- Database or persistence availability failures leave the message pending.
- Successful and controlled failed outcomes are acknowledged only after commit.

The default stale-claim threshold is 30 minutes to avoid recovering ordinary
analysis work too aggressively. Long-running production workers will need a
heartbeat before that threshold can be reduced safely.

## Consequences

- The complete submission-to-result path now exists behind explicit runtime
  configuration.
- API and worker releases remain independent, but schema compatibility becomes
  a cross-application contract that CI must protect.
- A one-message command is easy to test and supervise but is not yet a complete
  production worker service.
- Authentication, ownership, cancellation, progress events, heartbeats,
  dead-letter handling, and deployment supervision remain later work.