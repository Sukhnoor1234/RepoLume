# Repository analysis API contract

- **Status:** Proposed
- **Version:** v1

This document defines the planned HTTP boundary for starting and inspecting a
repository analysis. The endpoints are not implemented in the API foundation
checkpoint.

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

The first implementation will accept only public GitHub repository URLs over
HTTPS. URL validation, redirects, clone limits, archive limits, and network
isolation must be implemented before this endpoint is enabled.

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

## Deferred decisions

- Authentication and ownership
- Idempotency and duplicate submissions
- Rate limits and repository size limits
- Progress reporting and cancellation
- Retention and deletion
- Callback or streaming behavior