# Checkpoint verification evidence

These screenshots record fresh local verification runs for reviewed project
checkpoints. Each image includes the branch, result, and capture date.

## Checkpoint 6

### API pytest

Command: `python -m pytest` from `apps/api`

Result: 55 tests passed.

![API pytest results](checkpoint-06-api-pytest.png)

### Worker pytest

Command: `python -m pytest` from `apps/worker`

Result: 48 tests passed.

![Worker pytest results](checkpoint-06-worker-pytest.png)

## Checkpoint 7

Branch: `feature/python-analysis`

Captured: August 1, 2026

### API pytest

Command: `python -m pytest` from `apps/api`

Result: 55 tests passed in 0.55 seconds.

![Checkpoint 7 API pytest results](checkpoint-07-api-pytest.png)

### Worker pytest

Command: `python -m pytest` from `apps/worker`

Result: 70 tests passed in 0.70 seconds.

![Checkpoint 7 worker pytest results](checkpoint-07-worker-pytest.png)

The screenshots are documentation artifacts rendered from the exact output of
fresh local runs. GitHub Actions remains the authoritative CI record after the
branch is pushed.

## Checkpoint 8

Branch: `feature/typescript-analysis`

Captured: August 2, 2026

### API pytest

Command: `python -m pytest` from `apps/api`

Result: 55 tests passed in 0.57 seconds.

![Checkpoint 8 API pytest results](checkpoint-08-api-pytest.png)

### Worker pytest

Command: `python -m pytest` from `apps/worker`

Result: 98 tests passed in 0.48 seconds.

![Checkpoint 8 worker pytest results](checkpoint-08-worker-pytest.png)

The screenshots are documentation artifacts rendered from the exact output of
fresh local runs. GitHub Actions remains the authoritative CI record after the
branch is pushed.

## Checkpoint 8.1

Branch: `feature/typescript-analysis-hardening`

Captured: August 2, 2026

### API pytest

Command: `python -m pytest` from `apps/api`

Result: 55 tests passed in 0.85 seconds.

![Checkpoint 8.1 API pytest results](checkpoint-08-1-api-pytest.png)

### Worker pytest

Command: `python -m pytest` from `apps/worker`

Result: 100 tests passed in 0.75 seconds.

![Checkpoint 8.1 worker pytest results](checkpoint-08-1-worker-pytest.png)

The screenshots are documentation artifacts rendered from the exact output of
fresh local runs. GitHub Actions remains the authoritative CI record after the
branch is pushed.

## Checkpoint 9

Branch: `feature/architecture-artifact`

Captured: August 3, 2026

### API pytest

Command: `python -m pytest` from `apps/api`

Result: 55 tests passed in 0.75 seconds.

![Checkpoint 9 API pytest results](checkpoint-09-api-pytest.png)

### Worker pytest

Command: `python -m pytest` from `apps/worker`

Result: 117 tests passed in 0.81 seconds.

![Checkpoint 9 worker pytest results](checkpoint-09-worker-pytest.png)

The screenshots are documentation artifacts rendered from the exact output of
fresh local runs. GitHub Actions remains the authoritative CI record after the
branch is pushed.

## Checkpoint 10

Branch: `feature/analysis-pipeline`

Captured: August 3, 2026

### API pytest

Command: `python -m pytest` from `apps/api`

Result: 55 tests passed in 0.63 seconds.

![Checkpoint 10 API pytest results](checkpoint-10-api-pytest.png)

### Worker pytest

Command: `python -m pytest` from `apps/worker`

Result: 128 tests passed in 0.93 seconds.

![Checkpoint 10 worker pytest results](checkpoint-10-worker-pytest.png)

The screenshots are documentation artifacts rendered from the exact output of
fresh local runs. GitHub Actions remains the authoritative CI record after the
branch is pushed.

## Checkpoint 11

Branch: `feature/analysis-api`

Captured: August 3, 2026

### API pytest

Command: `python -m pytest` from `apps/api`

Result: 71 tests passed in 1.05 seconds.

![Checkpoint 11 API pytest results](checkpoint-11-api-pytest.png)

### Worker pytest

Command: `python -m pytest` from `apps/worker`

Result: 128 tests passed in 0.77 seconds.

![Checkpoint 11 worker pytest results](checkpoint-11-worker-pytest.png)

The screenshots are documentation artifacts rendered from the exact output of
fresh local runs. GitHub Actions remains the authoritative CI record after the
branch is pushed.

## Checkpoint 12

Branch: `feature/analysis-storage`

Captured: August 3, 2026

### API pytest

Command: `python -m pytest` from `apps/api`

Result: 96 tests passed in 4.90 seconds.

![Checkpoint 12 API pytest results](checkpoint-12-api-pytest.png)

### Worker pytest

Command: `python -m pytest` from `apps/worker`

Result: 128 tests passed in 1.47 seconds.

![Checkpoint 12 worker pytest results](checkpoint-12-worker-pytest.png)

The screenshots are documentation artifacts rendered from the exact output of
fresh local runs. GitHub Actions remains the authoritative CI record after the
branch is pushed. API CI also applies the PostgreSQL migration, checks model
and migration drift, and runs storage tests against PostgreSQL 17.

## Checkpoint 13

Branch: `feature/analysis-queue`

Captured: August 3, 2026

### API pytest

Command: `python -m pytest` from `apps/api`

Result: 115 tests passed in 2.45 seconds; the live Redis integration test is
separated for CI.

![Checkpoint 13 API pytest results](checkpoint-13-api-pytest.png)

### Worker pytest

Command: `python -m pytest` from `apps/worker`

Result: 158 tests passed in 1.13 seconds; the live Redis integration test is
separated for CI.

![Checkpoint 13 worker pytest results](checkpoint-13-worker-pytest.png)

The screenshots are documentation artifacts rendered from the exact output of
fresh local runs. GitHub Actions starts Redis 8.8.1 and runs the separated API
publisher and worker consumer-group integration tests. API CI also applies the
PostgreSQL migration and checks model/migration drift.

## Checkpoint 14

Branch: `feature/analysis-runtime`

Captured: August 3, 2026

### API pytest

Command: `python -m pytest` from `apps/api`

Result: 127 tests passed in 3.66 seconds; the live Redis integration test is
separated for CI.

![Checkpoint 14 API pytest results](checkpoint-14-api-pytest.png)

### Worker pytest

Command: `python -m pytest` from `apps/worker`

Result: 181 tests passed in 2.30 seconds; the live Redis and PostgreSQL
integration tests are separated for CI.

![Checkpoint 14 worker pytest results](checkpoint-14-worker-pytest.png)

The screenshots are documentation artifacts rendered from the exact output of
fresh local runs. GitHub Actions starts PostgreSQL 17 and Redis 8.8.1, then
verifies real queue delivery, durable completion, and acknowledgement.

## Checkpoint 15

Branch: `feature/web-analysis-flow`

Captured: August 12, 2026

### API pytest

Command: `python -m pytest` from `apps/api`

Result: 127 tests passed in 7.11 seconds; the live Redis integration test is
separated for CI.

![Checkpoint 15 API pytest results](checkpoint-15-api-pytest.png)

### Worker pytest

Command: `python -m pytest` from `apps/worker`

Result: 181 tests passed in 6.71 seconds; the live Redis and PostgreSQL
integration tests are separated for CI.

![Checkpoint 15 worker pytest results](checkpoint-15-worker-pytest.png)

The web verification also completed a production Vinext build, five rendered
and route-level tests, ESLint, a zero-vulnerability production dependency
audit, and desktop and mobile browser checks.

## Checkpoint 16

Branch: `feature/architecture-explorer`

Captured: August 12, 2026

### API pytest

Command: `python -m pytest` from `apps/api`

Result: 127 tests passed in 2.60 seconds; the live Redis integration test is
separated for CI.

![Checkpoint 16 API pytest results](checkpoint-16-api-pytest.png)

### Worker pytest

Command: `python -m pytest` from `apps/worker`

Result: 181 tests passed in 1.55 seconds; the live Redis and PostgreSQL
integration tests are separated for CI.

![Checkpoint 16 worker pytest results](checkpoint-16-worker-pytest.png)

The web verification also completed a production Vinext build, five rendered
and route-level tests, ESLint, a zero-vulnerability production dependency
audit, and an end-to-end browser check from repository submission through
source-evidence node selection.
