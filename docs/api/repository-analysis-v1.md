# Repository analysis API contract

- **Status:** Preflight implemented; analysis submission proposed
- **Version:** v1

This document defines the planned HTTP boundary for starting and inspecting a
repository analysis.

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
and requirements for future retrieval are documented in
[repository intake security](../security/repository-intake.md).

## Submit an analysis

`POST /v1/analyses`

```json
{
  "repository_url": "https://github.com/owner/repository",
  "ref": "main"
}
```

A valid request will eventually return `202 Accepted`:

```json
{
  "analysis_id": "01JEXAMPLE0000000000000000",
  "status": "queued"
}
```

The worker now implements commit-pinned public GitHub retrieval, redirect
validation, bounded streaming, archive inspection, safe extraction, and
temporary cleanup. It can produce versioned Python and TypeScript/JavaScript
analysis artifacts and compose them into one language-neutral repository
architecture graph. An internal pipeline coordinates that complete run and
returns only after temporary cleanup succeeds. This endpoint remains disabled
until queue delivery, ownership, and persistence are implemented.

## Inspect an analysis

`GET /v1/analyses/{analysis_id}`

The planned lifecycle states are `queued`, `cloning`, `analyzing`, `completed`,
and `failed`. A completed response will link to architecture data through
separate endpoints rather than embedding the complete graph in this status
response.

The allowed transitions are documented in the
[analysis worker lifecycle](../worker/lifecycle.md).

## Error envelope

Errors use one stable top-level shape:

```json
{
  "error": {
    "code": "repository_not_supported",
    "message": "The repository could not be analyzed."
  }
}
```

Messages are safe for users. Sensitive exception details, credentials, source
contents, and internal network information must never be included.

Preflight failures use one of these machine-readable codes:

- `repository_url_invalid`
- `repository_host_not_supported`
- `repository_path_invalid`
- `repository_ref_invalid`
- `validation_error` for an invalid request body

## Deferred decisions

- Authentication and ownership
- Idempotency and duplicate submissions
- Rate limits and final repository size limits
- Progress reporting and cancellation
- Retention and deletion
- Callback or streaming behavior
