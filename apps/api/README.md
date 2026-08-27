# RepoLume API

This directory contains the HTTP API for RepoLume.

## Current milestone

The API exposes service health, generated OpenAPI documentation, consistent
error responses, repository preflight, and versioned analysis job routes. A
transactional storage repository now persists lifecycle state and completed
architecture artifacts behind PostgreSQL-ready SQLAlchemy models and Alembic
migrations. Job creation now writes a transactional outbox event, and an
isolated publisher can deliver it to Redis Streams with recoverable leases. The
durable HTTP adapter and background publisher are installed only when the
analysis runtime is explicitly enabled. Otherwise, analysis routes return a
safe `503`. Repository analysis never runs inside an API request.

Completed artifacts also support deterministic evidence queries. This first
retrieval layer ranks source-located architecture nodes without calling an LLM
or presenting generated prose as fact.

The HTTP boundary is documented in the
[repository analysis API contract](../../docs/api/repository-analysis-v1.md),
evidence ranking is documented in
[repository evidence retrieval](../../docs/api/repository-evidence-retrieval.md),
and persistence behavior is documented in
[analysis job storage](../../docs/api/analysis-storage.md) and the
[analysis request queue](../../docs/worker/analysis-queue.md).

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

A local API started without the analysis runtime intentionally returns
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

`REPOLUME_DATABASE_URL` configures storage and must use a
`postgresql+psycopg://` URL containing a database name. Keep credentials in the
deployment environment rather than repository files.

Apply the current migration before starting a configured deployment:

```bash
python -m alembic upgrade head
```

Set `REPOLUME_ANALYSIS_RUNTIME_ENABLED=true`, `REPOLUME_DATABASE_URL`, and
`REPOLUME_REDIS_URL` to enable durable submission and background publication.
Credentials remain in deployment environment variables and are redacted from
diagnostics. Apply migrations before enabling the runtime.
