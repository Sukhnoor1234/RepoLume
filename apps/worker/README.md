# RepoLume Worker

This directory contains the asynchronous analysis-worker boundary for RepoLume.

## Current milestone

The worker validates runtime configuration, enforces the analysis-job
lifecycle, and can safely retrieve an isolated snapshot of a public GitHub
repository. Its internal pipeline connects retrieval, Python and
TypeScript/JavaScript analysis, language-neutral architecture composition, and
temporary cleanup without executing repository code. The bounded runtime now
connects Redis consumer-group delivery to that pipeline and persists lifecycle
state, safe failures, and completed architecture results in PostgreSQL before
acknowledgement.

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
[repository analysis pipeline](../../docs/worker/analysis-pipeline.md). Queue
delivery is documented in the
[analysis request queue](../../docs/worker/analysis-queue.md) and
[analysis runtime wiring](../../docs/worker/analysis-runtime.md).

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
when the database and Redis URLs are absent. With both configured, use:

```bash
python -m repolume_worker --once
```

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

The queue adapter reads `REPOLUME_REDIS_URL`, with optional stream, consumer
group, and stale-claim settings documented in
[analysis request queue](../../docs/worker/analysis-queue.md) and
[analysis runtime wiring](../../docs/worker/analysis-runtime.md).
