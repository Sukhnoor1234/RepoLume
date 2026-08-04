# Repository analysis API contract

- **Status:** HTTP boundary implemented; durable job adapter pending
- **Version:** v1
- **Checkpoint:** 11

This document defines the HTTP boundary for submitting, inspecting, and reading
the architecture result of a repository analysis. The routes are implemented
against an injected job-service interface. The default application does not
pretend to queue work: it returns a safe `503 Service Unavailable` until a real
queue and persistence adapter is configured.

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

The API does not run retrieval or static analysis in the request process. A
later adapter will persist the initial job and publish it for the worker.

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

The application factory accepts an `AnalysisJobService`. Its adapter must:

- create a durable queued job and return its identifier
- read current lifecycle state and safe terminal failure details
- return a validated architecture artifact only after completion
- map missing and incomplete jobs to the service exceptions defined by the API

The default adapter fails closed. Checkpoint 12 provides a transactional storage
repository for job state and architecture artifacts, but it is intentionally not
an `AnalysisJobService` yet. Submission must coordinate durable creation with
queue publication before the adapter can safely return `202`.

Route tests use an isolated fake adapter and verify normalization, every
response shape, stable error mapping, result gating, and the generated OpenAPI
document. Storage behavior is documented in
[analysis job storage](analysis-storage.md).

## Deferred decisions

- retention, deletion, backup, and restore operations
- Redis queue delivery, acknowledgement, retries, and abandoned-job recovery
- Authentication, authorization, and job ownership
- Idempotency and duplicate submissions
- Rate limits
- Progress streaming and cancellation
