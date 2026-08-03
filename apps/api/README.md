# RepoLume API

This directory contains the HTTP API for RepoLume.

## Current milestone

The API exposes service health, generated OpenAPI documentation, consistent
error responses, repository preflight, and versioned analysis job routes.
Submission, lifecycle inspection, and architecture retrieval use an injected
job-service boundary. The default adapter returns a safe `503` until durable
queue and persistence integrations are configured. Repository analysis never
runs inside the API request process.

The planned ingestion boundary is documented in the
[repository analysis API contract](../../docs/api/repository-analysis-v1.md).

## Local setup

Create a Python 3.12 virtual environment:

```bash
python -m venv .venv
```

Activate `.venv` with `source .venv/bin/activate` on macOS/Linux or
`.venv\Scripts\Activate.ps1` in Windows PowerShell. Then install the application
with its development tools:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Start the development server:

```bash
python -m uvicorn repolume_api.main:app --reload
```

The health endpoint is available at `http://127.0.0.1:8000/health` and the
interactive API documentation is available at `http://127.0.0.1:8000/docs`.

Validate a repository reference:

```bash
curl -X POST http://127.0.0.1:8000/v1/repositories/preflight \
  -H "Content-Type: application/json" \
  -d '{"repository_url":"https://github.com/octocat/Hello-World","ref":"main"}'
```

This only checks the submitted format. It does not prove that the repository
exists, is public, or can be downloaded.

Submit an analysis through a configured job service:

```bash
curl -X POST http://127.0.0.1:8000/v1/analyses \
  -H "Content-Type: application/json" \
  -d '{"repository_url":"https://github.com/octocat/Hello-World","ref":"main"}'
```

A local API started without a durable job adapter intentionally returns
`503 analysis_service_unavailable` for analysis routes. Preflight remains
available because it performs only local validation.

## Quality checks

```bash
python -m ruff format --check .
python -m ruff check .
python -m pytest
python -m pip check
```

## Configuration

`REPOLUME_ENVIRONMENT` controls the environment reported by the service. Its
allowed values are `development`, `test`, `staging`, and `production`; the
default is `development`.