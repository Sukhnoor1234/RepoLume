# ADR 0012: Sample-first public web deployment

- Status: Accepted
- Date: 2026-09-18

## Context

RepoLume needs a public portfolio URL before the complete FastAPI, PostgreSQL,
Redis, and analysis-worker runtime is hosted. Publishing an upload form that
silently depends on an unavailable private backend would create a broken first
impression for reviewers.

The web application already contains built-in repositories that demonstrate
the architecture explorer and source-cited answer workflow without external
services.

## Decision

Deploy the Vinext web application to Cloudflare Workers as a sample-first public
demo. When `REPOLUME_API_URL` is not configured, the interface explicitly shows
public demo mode, disables live repository submission, and keeps the built-in
samples fully interactive.

The deployment includes:

- a no-secret `/api/health` endpoint;
- a repeatable Wrangler build and deployment command;
- a post-deployment smoke test for the page, health endpoint, and sample data;
- a manually triggered GitHub Actions production workflow; and
- no Cloudflare account identifiers, API tokens, or backend URLs in source.

Live analysis can be enabled later by deploying the API runtime and setting a
valid `REPOLUME_API_URL` binding. The web proxy continues to validate that URL
and fails closed when it is missing or invalid.

## Consequences

- Reviewers receive a reliable, honest demo even before backend hosting is
  complete.
- The repository can remain private while the compiled demo is public.
- Publishing requires a one-time Cloudflare login or repository secrets.
- The public demo proves the product interaction, while real repository intake
  remains documented as a verified local flow until the backend is hosted.
