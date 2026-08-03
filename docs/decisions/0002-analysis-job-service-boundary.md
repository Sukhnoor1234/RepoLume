# ADR 0002: Keep analysis execution behind a job-service boundary

- **Status:** Accepted
- **Date:** 2026-08-03

## Context

Repository analysis performs network retrieval, archive validation, static
analysis, graph composition, and cleanup. A complete run can outlive an HTTP
request and must eventually support retries, ownership, progress, and durable
results. Running that work directly inside FastAPI would couple request latency
to untrusted repository size and make recovery unreliable.

Checkpoint 11 needs a real HTTP contract before the final database and queue
technologies are connected.

## Decision

The API exposes analysis submission, status, and architecture routes through an
`AnalysisJobService` interface. The interface owns three operations:

- accept a normalized repository as a queued job
- read a job snapshot by analysis identifier
- read the architecture artifact for a completed job

The application factory receives an adapter explicitly. Without one, the API
returns `503 analysis_service_unavailable`. It never creates an in-memory job or
runs the worker pipeline inside the request process.

The future durable adapter will persist job state and publish work to the worker.
The worker remains responsible for repository retrieval, analysis, composition,
cleanup, and safe failure production.

## Consequences

### Benefits

- HTTP contracts can be tested without Redis, PostgreSQL, or GitHub access.
- Production cannot acknowledge work that was never durably queued.
- The API and worker remain independently deployable.
- Queue and storage technology can change without changing route handlers.
- Completed graph responses are validated before they cross the HTTP boundary.

### Tradeoffs

- Submission returns `503` until a durable adapter is installed.
- The worker and API currently maintain separate typed representations of the
  documented architecture contract.
- An integration test will be required when the durable adapter is added.

## Guardrails

- Do not execute repository analysis inside an API request.
- Do not use process memory as the production job store.
- Return `202` only after the job service accepts the queued job.
- Expose architecture only for successfully completed jobs.
- Persist and return only user-safe failure codes and messages.
