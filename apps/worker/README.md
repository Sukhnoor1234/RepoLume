# RepoLume Worker

This directory contains the asynchronous analysis-worker boundary for RepoLume.

## Current milestone

The worker currently validates its runtime configuration, reports readiness,
and enforces the planned analysis-job lifecycle. It does not connect to a
queue, clone repositories, parse source code, or persist results yet.

The state rules are documented in the
[analysis worker lifecycle](../../docs/worker/lifecycle.md).

## Local setup

Create a Python 3.12 virtual environment:

```bash
python -m venv .venv
```

Activate `.venv` with `source .venv/bin/activate` on macOS/Linux or
`.venv\Scripts\Activate.ps1` in Windows PowerShell. Then install the worker
with its development tools:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Run the readiness check:

```bash
python -m repolume_worker --check
```

The JSON result intentionally reports `"queue_backend": "not_configured"`
until the queue milestone is implemented.

## Quality checks

```bash
python -m ruff format --check .
python -m ruff check .
python -m pytest
python -m pip check
```

## Configuration

`REPOLUME_ENVIRONMENT` controls the environment reported by the worker. Its
allowed values are `development`, `test`, `staging`, and `production`; the
default is `development`.
