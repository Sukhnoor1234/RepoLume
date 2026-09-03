# ADR 0010: Add sample repositories for the first-click demo

- **Status:** Accepted
- **Date:** 2026-08-29

## Context

RepoLume now has a real analysis workflow, architecture graph, evidence
retrieval, and grounded answers. For internship review, the first minute
matters. A reviewer should be able to see the core experience even if the live
API, worker, Redis, or PostgreSQL services are not running.

## Decision

Add a small web-layer sample repository catalog. Each sample has a stable
analysis identifier, a static architecture artifact, and static grounded answer
citations. The sample routes use the same local `/api/analyses/{id}` paths as
the live flow and only intercept known sample identifiers.

Normal analysis identifiers still proxy to FastAPI. The live repository
submission form remains unchanged.

## Consequences

- The portfolio demo works immediately without sign-up or backend setup.
- Browser tests can cover the complete architecture and answer experience.
- The sample data must stay clearly labeled as demo data.
- Future saved analyses can replace these fixtures without changing the UI
  contract.
