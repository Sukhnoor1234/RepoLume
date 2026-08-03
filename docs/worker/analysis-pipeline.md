# Repository analysis pipeline

- **Status:** Implemented as an isolated worker capability
- **Checkpoint:** 10
- **Result schema:** 1.0

The repository analysis pipeline connects RepoLume's secure retrieval, source
analyzers, and architecture composer into one complete in-memory worker run. It
accepts a queued job and normalized GitHub coordinates, and returns only after
the temporary repository has been cleaned up successfully.

```mermaid
flowchart TD
    Q["Queued analysis job"] --> C["cloning"]
    C --> R["Retrieve commit-pinned snapshot"]
    R --> A["analyzing"]
    A --> P["Python analyzer"]
    A --> T["TypeScript/JavaScript analyzer"]
    P --> G["Architecture composer"]
    T --> G
    G --> X["Exit retrieval context and clean temporary source"]
    X --> D["completed"]
    R --> F["failed"]
    A --> F
    G --> F
    X --> F
```

## Successful result

A completed version 1 result contains:

- the analysis identifier and terminal `completed` status
- the full ordered lifecycle history
- provider, owner, repository, requested ref, and immutable commit SHA
- archive file count and expanded byte count
- the language-neutral repository architecture artifact

The temporary archive and extraction path are deliberately absent. Result JSON
contains repository-relative evidence only and remains usable after the
retrieval context exits.

## Lifecycle rules

The pipeline accepts an `AnalysisJob` in `queued` state and records:

```text
queued -> cloning -> analyzing -> completed
```

A retrieval failure records:

```text
queued -> cloning -> failed
```

Analysis, composition, or cleanup failures record:

```text
queued -> cloning -> analyzing -> failed
```

A job that is not queued is rejected before repository retrieval. Completion is
recorded only after the retrieval context exits. If temporary cleanup fails,
the run is failed and never exposes a completed result.

## Failure contract

Controlled retrieval and source-analysis failures preserve their existing safe
code and message. Invalid internal architecture composition is mapped to
`architecture_composition_failed`. Any other exception is mapped to
`analysis_failed` with a generic user-safe message.

The raised pipeline error includes:

- analysis identifier
- safe machine-readable code
- safe message
- terminal `failed` status
- lifecycle history

Raw parser details, response bodies, source contents, credentials, temporary
paths, and exception text are not copied into the safe message. The original
exception remains available only as the in-process cause for logs that apply
their own redaction policy.

## Dependency boundaries

The pipeline requires a repository retriever and uses the production Python
analyzer, TypeScript/JavaScript analyzer, and architecture composer by default.
Each boundary can be replaced in tests, so regression tests use an isolated
fake retrieval context and never depend on live GitHub access.

The production retriever still owns network validation, archive limits,
extraction safety, and physical cleanup. The pipeline owns ordering, lifecycle,
result construction, and safe cross-boundary failure behavior.

## Intentional limitations

Checkpoint 10 does not include:

- an API analysis-submission endpoint
- queue delivery, claims, acknowledgements, or retries
- database persistence, retention, or result retrieval
- authentication, authorization, or job ownership
- progress streaming or cancellation
- container-level outbound network policy
- UI visualization or AI features

The pipeline is ready to be called by a later queue consumer or controlled local
integration without changing the analyzer and architecture contracts.
