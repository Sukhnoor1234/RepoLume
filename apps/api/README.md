# RepoLume API

This directory contains the HTTP API for RepoLume.

## Current milestone

The API currently exposes service health, generated OpenAPI documentation, and
consistent framework error responses. Repository ingestion, persistence,
background jobs, authentication, and AI features are intentionally not
implemented yet.

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