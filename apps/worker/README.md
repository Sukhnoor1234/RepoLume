# RepoLume Worker

This directory contains the asynchronous analysis-worker boundary for RepoLume.

## Current milestone

The worker validates runtime configuration, enforces the analysis-job
lifecycle, and can safely retrieve an isolated snapshot of a public GitHub
repository. Its internal pipeline connects retrieval, Python and
TypeScript/JavaScript analysis, language-neutral architecture composition, and
temporary cleanup without executing repository code. The pipeline is not
connected to a queue or API submission yet, and the worker does not persist
results.

The state rules are documented in the
[analysis worker lifecycle](../../docs/worker/lifecycle.md). The network, archive,
resource, and cleanup boundaries are documented in
[repository retrieval](../../docs/worker/repository-retrieval.md). The artifact,
confidence, and parser boundaries are documented in
[Python static analysis](../../docs/worker/python-static-analysis.md),
[TypeScript and JavaScript static analysis](../../docs/worker/typescript-static-analysis.md),
and the
[repository architecture artifact](../../docs/worker/repository-architecture-artifact.md).
The complete orchestration and result boundary is documented in the
[repository analysis pipeline](../../docs/worker/analysis-pipeline.md).

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
