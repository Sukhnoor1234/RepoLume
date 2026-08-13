# ADR 0006: Keep the analysis API behind a same-origin web proxy

- **Status:** Accepted
- **Date:** 2026-08-12

## Context

The first interactive web workflow needs to submit analysis requests and poll
their lifecycle state. Calling FastAPI directly from the browser would expose
the internal API address, require browser-facing CORS policy, and couple the
client bundle to deployment topology.

The web application must also fail safely when no API deployment is configured
and must not render unvalidated service responses as trusted UI state.

## Decision

The browser calls same-origin Next.js route handlers under `/api/analyses`.
Those handlers validate the small request boundary and proxy it to the FastAPI
v1 contract using the server-only `REPOLUME_API_URL` setting.

The proxy:

- accepts only HTTP or HTTPS API base URLs without embedded credentials
- never includes the configured API address in a browser response
- disables response caching for analysis state
- bounds each upstream request to ten seconds
- limits upstream JSON responses to one megabyte
- replaces connection and malformed-response details with safe error envelopes

The client independently validates submission, status, and completed
architecture response shapes before using them. It polls only while the job is
active and stops on completion, failure, service error, or component cleanup.

## Consequences

- Browser deployment remains same-origin and does not depend on API CORS.
- The web server becomes the public transport boundary for the API.
- Every deployed web environment must configure `REPOLUME_API_URL` to enable
  analysis; otherwise it returns a safe `503`.
- Authentication, rate limiting, and streaming remain later decisions.
