# Local development flow

This runbook starts the real RepoLume analysis path on your laptop:

```text
web form -> FastAPI -> Redis queue -> worker -> GitHub clone -> static analysis -> PostgreSQL -> web explorer
```

The built-in samples are still useful for quick demos, but this flow is for
testing an actual public GitHub repository URL.

## 1. Start local infrastructure

From the repository root:

```powershell
docker compose -f infra/local/docker-compose.yml up -d
```

This starts PostgreSQL and Redis with local-only development settings. The
database password in the compose file is not a production secret.

## 2. Start the API

In a new terminal:

```powershell
cd apps/api
.\.venv\Scripts\Activate.ps1
$env:REPOLUME_ANALYSIS_RUNTIME_ENABLED = "true"
$env:REPOLUME_DATABASE_URL = "postgresql+psycopg://repolume:repolume_dev_password@localhost:5432/repolume"
$env:REPOLUME_REDIS_URL = "redis://localhost:6379/0"
python -m alembic upgrade head
python -m uvicorn repolume_api.main:app --reload --port 8000
```

The API accepts repository submissions, stores analysis jobs, and publishes
worker messages through Redis.

## 3. Start the worker

In another terminal:

```powershell
cd apps/worker
.\.venv\Scripts\Activate.ps1
$env:REPOLUME_DATABASE_URL = "postgresql+psycopg://repolume:repolume_dev_password@localhost:5432/repolume"
$env:REPOLUME_REDIS_URL = "redis://localhost:6379/0"
python -m repolume_worker --loop
```

The worker keeps listening for analysis jobs. Leave this terminal open while
you demo the live repository flow.

## 4. Start the web app

In another terminal:

```powershell
cd apps/web
Copy-Item .dev.vars.example .dev.vars
npm run dev
```

Vinext runs the app in Cloudflare's local worker runtime, so local server
bindings come from the ignored `.dev.vars` file. The checked-in example points
to the local FastAPI service and contains no secret values.

Open `http://localhost:3000`, paste a public GitHub repository URL, and click
**Analyze repository**.

## Good small repositories to try first

- `https://github.com/octocat/Hello-World`
- A small personal TypeScript or Python repository

Start with small repositories while testing locally. Large repositories can
take longer to clone and analyze.

## Stop everything

Stop the API, worker, and web terminals with `Ctrl+C`.

To stop local infrastructure:

```powershell
docker compose -f infra/local/docker-compose.yml down
```

To also delete local database and Redis data:

```powershell
docker compose -f infra/local/docker-compose.yml down -v
```
