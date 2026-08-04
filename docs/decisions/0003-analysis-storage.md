# ADR 0003: Store analysis state relationally and architecture as JSONB

- **Status:** Accepted
- **Date:** 2026-08-03

## Context

Analysis lifecycle state is updated and filtered frequently, while a repository
architecture is produced and consumed as one versioned graph document. RepoLume
needs atomic completion, safe concurrent worker updates, schema migrations, and
a clear path to retention without coupling the HTTP API to worker internals.

## Decision

Use PostgreSQL as the durable system of record. Store job identity, lifecycle,
failures, timestamps, and concurrency version in `analysis_jobs`. Store one
strictly validated architecture document per completed job in
`analysis_architectures.payload` using JSONB.

Use SQLAlchemy for explicit transactional repository operations and Alembic for
reviewable migrations. Lifecycle changes use compare-and-set predicates against
the expected status. Completion and architecture insertion share one
transaction.

The API job-service boundary is not connected in this checkpoint. Enabling
submission requires a later adapter that coordinates durable creation with
queue publication.

## Consequences

### Benefits

- Lifecycle queries and future worker claims use normal relational indexes.
- Graph schema evolution does not require a table for every node property.
- Job completion cannot commit independently from its architecture.
- Stale workers receive conflicts instead of overwriting newer state.
- Migrations can be rendered and reviewed before deployment.

### Tradeoffs

- JSONB graph internals are less convenient for complex SQL graph traversal.
- API and worker contracts must remain versioned and integration-tested.
- Queue publication will require an outbox or an equivalent atomic handoff.
- PostgreSQL operations, backups, and retention still need deployment design.

## Guardrails

- Do not log unredacted database URLs.
- Do not store raw exception text in failure fields.
- Do not bypass lifecycle compare-and-set updates.
- Do not mark a job completed without inserting its validated architecture in
  the same transaction.
- Do not enable API submission until durable queue publication is designed.
