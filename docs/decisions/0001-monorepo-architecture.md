# ADR 0001: Use a monorepo for the initial product

- **Status:** Accepted
- **Date:** 2026-07-30

## Context

RepoLume requires a browser application, an HTTP API, and an asynchronous
analysis worker. These applications use different runtimes but share one
product contract, release roadmap, and integration-test surface.

For the first public version, development will be performed by a small team and
optimized for clear review, reproducible local setup, and visible portfolio
documentation.

## Decision

RepoLume will use one Git repository containing three independently deployable
applications:

- `web`: the Next.js user interface and architecture explorer
- `api`: the FastAPI HTTP and streaming API
- `worker`: the asynchronous repository-analysis process

Shared contracts, documentation, development infrastructure, and integration
tests will live alongside the applications at the repository root. Each
application will retain its own runtime boundaries, dependency manifest, and
deployment configuration.

The precise directory layout will be established when the applications are
scaffolded. This decision establishes the ownership and deployment boundaries,
not a dependency on a specific monorepo orchestration tool.

## Consequences

### Benefits

- Product changes spanning the web, API, and worker can be reviewed together.
- Architecture documents and contracts remain versioned with their consumers.
- Local development and continuous integration can exercise the complete
  workflow from one checkout.
- The repository presents the system as one coherent portfolio project.

### Tradeoffs

- JavaScript/TypeScript and Python tooling must coexist without hiding their
  runtime boundaries.
- Continuous integration should avoid rebuilding unaffected applications as
  the project grows.
- Independent deployments require explicit application-level configuration
  even though the source is stored together.

## Guardrails

- The web application must not import worker or API implementation code.
- Communication between applications must use documented interfaces.
- Runtime dependencies remain scoped to the application that uses them.
- A future split into multiple repositories requires a new architecture
  decision and a demonstrated operational need.
