<p align="center">
  <img src="docs/assets/repolume-readme-banner.svg" alt="RepoLume — understand any codebase before you touch it" width="100%" />
</p>

<p align="center">
  <strong>Upload a public GitHub repository. Get an interactive architecture map and source-cited answers.</strong>
</p>

<p align="center">
  <a href="https://github.com/Sukhnoor1234/RepoLume/actions/workflows/web-ci.yml"><img src="https://github.com/Sukhnoor1234/RepoLume/actions/workflows/web-ci.yml/badge.svg" alt="Web checks" /></a>
  <a href="https://github.com/Sukhnoor1234/RepoLume/actions/workflows/api-ci.yml"><img src="https://github.com/Sukhnoor1234/RepoLume/actions/workflows/api-ci.yml/badge.svg" alt="API checks" /></a>
  <a href="https://github.com/Sukhnoor1234/RepoLume/actions/workflows/worker-ci.yml"><img src="https://github.com/Sukhnoor1234/RepoLume/actions/workflows/worker-ci.yml/badge.svg" alt="Worker checks" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-53d6e8" alt="MIT License" /></a>
  <img src="https://img.shields.io/badge/status-active%20development-f1bd70" alt="Active development" />
</p>

<p align="center">
  <a href="#what-is-repolume">What it does</a> ·
  <a href="#try-the-60-second-demo">Demo</a> ·
  <a href="#how-it-works">Architecture</a> ·
  <a href="#run-it-locally">Local setup</a> ·
  <a href="#roadmap">Roadmap</a>
</p>

---

## What is RepoLume?

RepoLume is an **AI architecture explorer** for understanding unfamiliar
codebases. Instead of stopping at a file tree, it retrieves a public GitHub
repository, analyzes its Python and TypeScript/JavaScript source, and turns the
result into an interactive system map.

Click through modules, symbols, entry points, and dependencies. Then ask a
question such as _“Where is signing implemented?”_ and inspect the exact file
and line range behind the answer.

> RepoLume is under active development. Static analysis, durable background
> jobs, the interactive explorer, built-in samples, and evidence-grounded
> repository questions work today. Model-generated explanations, hosted
> deployment, security insights, and maintainability scoring are on the
> roadmap.

## Why RepoLume?

Opening a new repository usually starts with the same slow process: search the
folders, trace imports, find entry points, and build a mental model of the
system from scattered clues. RepoLume makes that model visible.

| Explore the system | Follow the evidence | Ask the repository |
| --- | --- | --- |
| Navigate a dependency graph instead of guessing from filenames. | Inspect the source location behind supported nodes and relationships. | Get conservative answers backed by numbered file and line citations. |

### Current highlights

- **Interactive architecture graph** powered by React Flow
- **Python analysis** using the standard AST
- **TypeScript and JavaScript analysis** using Tree-sitter
- **Source-linked repository answers** with file and line citations
- **Durable asynchronous processing** with PostgreSQL and Redis Streams
- **Safe public-repository ingestion** with archive and extraction limits
- **Instant sample repositories** for a no-backend walkthrough
- **Three CI pipelines** covering the web, API, worker, and live integrations

## Verified on a real repository

Checkpoint 22 ran the complete stack against
[`pallets/itsdangerous`](https://github.com/pallets/itsdangerous):

| Result | Verified output |
| --- | ---: |
| Architecture nodes | 79 |
| Modules | 15 |
| Symbols | 43 |
| Dependencies | 80 |
| Repository question | “Where is signing implemented?” |
| Cited result | `src/itsdangerous/signer.py:15-28` |

The request travelled through the web app, FastAPI, PostgreSQL, Redis, the
analysis worker, and back to the interactive explorer. See the
[checkpoint evidence](docs/evidence/README.md#checkpoint-22) for the recorded
test results.

## How it works

```mermaid
flowchart LR
    A[Public GitHub repository] --> B[FastAPI submission]
    B --> C[(PostgreSQL)]
    B --> D[Redis Stream]
    D --> E[Analysis worker]
    E --> F[Python AST + Tree-sitter]
    F --> C
    C --> G[Interactive architecture explorer]
    G --> H[Source-cited repository answers]
```

RepoLume is a monorepo with three independently runnable applications:

```text
apps/
├── web/       Next.js interface and React Flow explorer
├── api/       FastAPI contracts, storage, and queue publication
└── worker/    Repository retrieval and static-analysis pipeline
```

Architecture choices and tradeoffs are recorded as
[architecture decision records](docs/decisions/).

## Try the 60-second demo

The built-in examples work without PostgreSQL, Redis, or the API:

```bash
cd apps/web
npm install
npm run dev
```

Open `http://localhost:3000`, select **Commerce platform**, and ask:

> How does an order get created?

RepoLume will display the architecture graph, a grounded answer, and the source
locations used to support it. The complete walkthrough is in the
[demo script](docs/demo-script.md).

## Run it locally

The full path runs the web app, FastAPI, PostgreSQL, Redis, and the worker.
Docker Desktop, Node.js 22+, and Python 3.12 are required.

<details>
<summary><strong>1. Start PostgreSQL and Redis</strong></summary>

```powershell
docker compose -f infra/local/docker-compose.yml up -d
```

</details>

<details>
<summary><strong>2. Start the API</strong></summary>

```powershell
cd apps/api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
$env:REPOLUME_ANALYSIS_RUNTIME_ENABLED = "true"
$env:REPOLUME_DATABASE_URL = "postgresql+psycopg://repolume:repolume_dev_password@localhost:5432/repolume"
$env:REPOLUME_REDIS_URL = "redis://localhost:6379/0"
python -m alembic upgrade head
python -m uvicorn repolume_api.main:app --reload --port 8000
```

</details>

<details>
<summary><strong>3. Start the worker</strong></summary>

```powershell
cd apps/worker
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
$env:REPOLUME_DATABASE_URL = "postgresql+psycopg://repolume:repolume_dev_password@localhost:5432/repolume"
$env:REPOLUME_REDIS_URL = "redis://localhost:6379/0"
python -m repolume_worker --loop
```

</details>

<details>
<summary><strong>4. Start the web app</strong></summary>

```powershell
cd apps/web
npm install
Copy-Item .dev.vars.example .dev.vars
npm run dev
```

</details>

For troubleshooting and shutdown commands, use the complete
[local development runbook](docs/local-development.md).

## Technology

| Layer | Current implementation |
| --- | --- |
| Web | Next.js 16, React 19, TypeScript, Tailwind CSS |
| Visualization | React Flow |
| API | Python 3.12, FastAPI, SQLAlchemy, Alembic |
| Analysis | Python AST, Tree-sitter for TypeScript/JavaScript |
| Data | PostgreSQL 17, Redis Streams |
| Infrastructure | Docker Compose, GitHub Actions |

## Quality and verification

The current checkpoint passes **338 automated tests and live integration
checks** across the three applications:

- 145 API tests plus one live Redis integration test
- 182 worker tests plus two live PostgreSQL/Redis integration tests
- 8 rendered-page and route-level web tests
- Ruff, ESLint, production builds, migration checks, and dependency audits in CI

Verification screenshots and results are kept in
[`docs/evidence`](docs/evidence/README.md), making each milestone reviewable.

## Version 1 scope

RepoLume v1 is focused on one reliable workflow:

1. Submit a public GitHub repository.
2. Generate an architecture and dependency graph.
3. Inspect modules, symbols, entry points, and source locations.
4. Ask repository questions and receive evidence-linked answers.
5. Clearly separate confirmed relationships from heuristic results.

Supported source languages: **Python, TypeScript, and JavaScript**.

## Roadmap

- [x] Monorepo and CI foundation
- [x] Safe public GitHub repository retrieval
- [x] Python and TypeScript/JavaScript static analysis
- [x] Durable PostgreSQL and Redis analysis runtime
- [x] Interactive architecture explorer
- [x] Evidence-grounded repository questions
- [x] Built-in sample repositories and demo path
- [x] Real repository end-to-end verification
- [ ] Hosted public deployment
- [ ] Maintainability and technical-debt insights
- [ ] Security findings and dependency vulnerability data
- [ ] Model-generated explanations and conversation history
- [ ] Pull-request analysis and change-impact estimates

## Contributing

RepoLume is currently being built checkpoint by checkpoint. Feature branches,
tests, and pull requests are required for changes. See
[`CONTRIBUTING.md`](CONTRIBUTING.md) for the workflow.

## License

RepoLume is available under the [MIT License](LICENSE).
