# ADR 0011: Local development runtime

## Status

Accepted

## Context

RepoLume now has a web app, FastAPI service, Redis-backed analysis queue,
PostgreSQL-backed analysis storage, and a Python worker. The built-in sample
repositories make the product easy to preview, but the live repository input
also needs a repeatable local setup so the project can be demonstrated honestly.

The worker previously supported `--once`, which is useful for CI and debugging
because it processes one queue message and exits. That mode is awkward for a
local product demo because a developer would need to manually restart the
worker for every submitted repository.

## Decision

RepoLume will support a local development runtime made of:

- PostgreSQL for durable analysis job and architecture storage.
- Redis Streams for the analysis queue.
- FastAPI with `REPOLUME_ANALYSIS_RUNTIME_ENABLED=true`.
- A long-running worker command, `python -m repolume_worker --loop`.
- The Next.js web app configured with `REPOLUME_API_URL`.

Local Postgres and Redis are provided through `infra/local/docker-compose.yml`.
The local compose file is only for development and does not define production
deployment infrastructure.

## Consequences

- A developer can paste a public GitHub repository URL into the local web app
  and have the API, queue, worker, and database path run together.
- CI and focused debugging can continue using `python -m repolume_worker --once`.
- The local demo requires Docker, GitHub network access, and small repositories
  while the analyzer is still early.
