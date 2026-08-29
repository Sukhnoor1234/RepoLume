# Repository analysis API contract

- **Status:** HTTP boundary and durable runtime implemented
- **Version:** v1
- **Checkpoint:** 14

This document defines the HTTP boundary for submitting, inspecting, and reading
the architecture result of a repository analysis. The routes are implemented
against an injected job-service interface. The production adapter is installed
only when the analysis runtime is explicitly enabled; otherwise the application
continues to return a safe `503 Service Unavailable`.

## Preflight a repository

`POST /v1/repositories/preflight`

```json
{
  "repository_url": "https://github.com/owner/repository.git",
  "ref": "main"
}
```

A valid request returns `200 OK` with a normalized reference:

```json
{
  "provider": "github",
  "owner": "owner",
  "repository": "repository",
  "canonical_url": "https://github.com/owner/repository",
  "ref": "main"
}
```

Preflight is local syntax validation only. It does not contact GitHub or prove
that the repository exists, is public, or is accessible. The security boundary
is documented in
[repository intake security](../security/repository-intake.md).

## Submit an analysis

`POST /v1/analyses`

```json
{
  "repository_url": "https://github.com/owner/repository",
  "ref": "main"
}
```

A configured job service returns `202 Accepted` only after it accepts the
normalized repository reference:

```json
{
  "analysis_id": "analysis_01JEXAMPLE",
  "status": "queued"
}
```

Without a configured adapter, the route returns:

```json
{
  "error": {
    "code": "analysis_service_unavailable",
    "message": "Repository analysis is temporarily unavailable."
  }
}
```

The API does not run retrieval or static analysis in the request process. The
durable adapter commits the job and its outbox event before returning; a
lifespan-owned publisher delivers that event outside the request.

## Inspect an analysis

`GET /v1/analyses/{analysis_id}`

The response contains lifecycle state and normalized repository identity, but
not the complete graph:

```json
{
  "analysis_id": "analysis_01JEXAMPLE",
  "status": "analyzing",
  "repository": {
    "provider": "github",
    "owner": "owner",
    "repository": "repository",
    "canonical_url": "https://github.com/owner/repository",
    "ref": "main"
  },
  "result_available": false,
  "failure": null
}
```

The allowed states are `queued`, `cloning`, `analyzing`, `completed`, and
`failed`. Failed jobs include only the safe failure code and message recorded by
the worker. Unknown identifiers return `404 analysis_not_found`.

## Read completed architecture

`GET /v1/analyses/{analysis_id}/architecture`

A completed job returns the versioned language-neutral artifact defined in
[repository architecture artifact](../worker/repository-architecture-artifact.md).
The HTTP schema includes languages, nodes, edges, diagnostics, and summary
counts. Repository-relative source locations remain attached as evidence.

Active or failed jobs return `409 analysis_not_completed`. The status response
must report `result_available: true` only for a completed job whose architecture
can be read.

## Query repository evidence

`POST /v1/analyses/{analysis_id}/evidence-query`

The request contains a question between 3 and 300 characters and an optional
result limit from 1 to 10:

```json
{
  "question": "Where is user authentication implemented?",
  "limit": 5
}
```

The response contains ranked architecture nodes with repository-relative line
ranges, matched terms, relationship counts, and confidence. It intentionally
does not contain generated prose. Active or failed jobs return
`409 analysis_not_completed`, matching architecture retrieval.

## Answer a repository question

`POST /v1/analyses/{analysis_id}/answer`

The request uses the same bounded question and evidence limit as the retrieval
route. The response contains a conservative answer, a grounding status, and up
to three numbered source citations. When no architecture evidence matches, the
API returns `insufficient_evidence`, an empty citation list, and a useful prompt
to make the question more specific instead of guessing.

The first answer composer is deterministic and does not call an external model.
Its behavior and limitations are documented in
[repository grounded answers](repository-grounded-answers.md).

## Error envelope

Errors use one stable top-level shape:

```json
{
  "error": {
    "code": "analysis_not_found",
    "message": "The requested analysis was not found."
  }
}
```

Messages are safe for users. Sensitive exception details, credentials, source
contents, and internal network information must never be included.

Repository input failures use:

- `repository_url_invalid`
- `repository_host_not_supported`
- `repository_path_invalid`
- `repository_ref_invalid`
- `validation_error` for an invalid request body or path identifier

Analysis boundary failures use:

- `analysis_service_unavailable`
- `analysis_not_found`
- `analysis_not_completed`

## Integration boundary

The application factory accepts either an injected `AnalysisJobService` or an
owned `AnalysisRuntime`. The production runtime:

- creates a durable queued job and outbox event in one transaction
- reads current lifecycle state and safe terminal failure details
- returns a validated architecture only after completion
- retries Redis publication outside HTTP requests
- maps missing, incomplete, corrupt, and unavailable storage states to stable
  service errors

Set `REPOLUME_ANALYSIS_RUNTIME_ENABLED=true` with the database and Redis URLs to
install it. The default adapter still fails closed. Runtime ownership and the
worker path are documented in
[analysis runtime wiring](../worker/analysis-runtime.md).

## Deferred decisions

- retention, deletion, backup, and restore operations
- Authentication, authorization, and job ownership
- Idempotency and duplicate submissions
- Rate limits
- Progress streaming and cancellation
