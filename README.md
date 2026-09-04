# RepoLume

> Understand any codebase before you touch it.

RepoLume is an **AI architecture explorer** that transforms a public GitHub
repository into an interactive software architecture map. It is designed to
help developers understand unfamiliar systems, trace how features work, and
ask questions that are answered with evidence from the source code.

## Project status

RepoLume is under active development. The repository contains the project
foundation, the first web interface, repository intake and analysis API
contracts, a bounded worker pipeline, PostgreSQL-backed analysis storage, and a
reliable Redis Stream runtime. When explicitly configured, the API can accept a
repository, publish its durable job, and expose the worker's persisted result.
The web interface can now submit repositories, follow their durable analysis
status, turn a completed result into an interactive source-linked graph, and
answer repository questions with conservative summaries backed by numbered
source citations. It also includes sample repositories that load instantly for
reviewers who want to try the product before a live analysis service is
configured. Model-generated explanations, conversation memory, and production
deployment remain in progress.

Development is intentionally milestone-based. Each checkpoint is reviewed and
verified before the next layer of the system is added.

## The problem

Understanding an unfamiliar repository often means manually searching through
folders, tracing imports, locating entry points, and reconstructing flows
across services. File trees show where code lives, but they do not explain how
the system fits together or what could be affected by a change.

RepoLume aims to turn that discovery work into an explorable model of the
codebase.

## Version 1 promise

The first public version will focus on one reliable workflow:

1. Submit a public GitHub repository.
2. Generate an interactive architecture and dependency map.
3. Inspect components, files, entry points, APIs, data stores, and
   relationships.
4. Ask repository questions and receive answers grounded in cited files and
   line ranges.
5. Load sample repositories without signing up or waiting for a worker.
6. Trace supported request flows and estimate the impact of changing or
   removing a file.

The initial analyzer will support TypeScript/JavaScript and Python. Results
derived through heuristics will be clearly distinguished from relationships
confirmed by static analysis.

## Planned technology

| Area | Planned tools |
| --- | --- |
| Web | Next.js, React, TypeScript, Tailwind CSS |
| Visualization | React Flow, ELK, Mermaid |
| API | Python, FastAPI |
| Analysis | Python AST, Tree-sitter, language-specific resolvers |
| Data | PostgreSQL, pgvector, Redis |
| AI | Retrieval-augmented generation, embeddings, LLM provider adapter |
| Delivery | Docker, GitHub Actions, managed cloud services |

Technology choices may be refined through documented architecture decisions as
the product develops.

## Planned repository structure

RepoLume will use a monorepo containing independently deployable web, API, and
analysis-worker applications. The decision and its tradeoffs are recorded in
[ADR 0001](docs/decisions/0001-monorepo-architecture.md).
The local development runtime is documented in
[ADR 0011](docs/decisions/0011-local-development-runtime.md).

## Run the web application

The current web foundation lives in `apps/web`.

```bash
cd apps/web
npm install
npm run dev
```

Set `REPOLUME_API_URL` to the FastAPI origin to enable repository submission,
status polling, completed architecture retrieval, evidence queries, and
grounded answer summaries. Without it, the web boundary returns a safe
service-unavailable response.

## 60-second demo path

For a quick portfolio walkthrough, run the web app and use one of the built-in
sample repositories. The samples do not require a configured API or worker, so
the first screen still shows the architecture explorer, source-linked graph,
and cited repository answers.

Suggested flow:

1. Start the web app with `npm run dev` from `apps/web`.
2. Open the local page and click **Commerce platform**.
3. Point out that the architecture graph is generated from repository-shaped
   analysis data, not a static mockup image.
4. Ask: “How does an order get created?”
5. Show the answer, cited files, and line ranges.

The live repository submission path is also implemented, but it needs the API
and worker services configured with `REPOLUME_API_URL`.

For the complete local flow with PostgreSQL, Redis, the API, the worker, and
the web app running together, use the [local development runbook](docs/local-development.md).

## Run the API

The API foundation lives in `apps/api` and requires Python 3.12.

```bash
cd apps/api
python -m venv .venv
```

Activate `.venv` with `source .venv/bin/activate` on macOS/Linux or
`.venv\Scripts\Activate.ps1` in Windows PowerShell, then run:

```bash
python -m pip install -e ".[dev]"
python -m uvicorn repolume_api.main:app --reload
```

The API exposes service health, repository preflight, and generated documentation.

## Run the worker

The analysis-worker foundation lives in `apps/worker` and requires Python 3.12.

```bash
cd apps/worker
python -m venv .venv
```

Activate `.venv` with `source .venv/bin/activate` on macOS/Linux or
`.venv\Scripts\Activate.ps1` in Windows PowerShell, then run:

```bash
python -m pip install -e ".[dev]"
python -m repolume_worker --check
```

The readiness command validates configuration without connecting. A
configured worker can process one recovered or new request with
`python -m repolume_worker --once`. Bounded one-message execution is intentional
for CI and debugging. For local demos, use `python -m repolume_worker --loop`
so the worker keeps processing submitted repositories until you stop it.

## Development workflow

Work is completed on focused feature branches and reviewed through pull
requests before it reaches `main`. See [CONTRIBUTING.md](CONTRIBUTING.md) for
the repository workflow and quality expectations.

## Roadmap

- Repository and engineering foundation
- Web, API, and worker application scaffolding
- Safe public-repository ingestion
- TypeScript and Python static analysis
- Interactive architecture explorer
- Evidence-grounded repository chat
- Maintainability and security insights
- Documentation, sample repositories, and public launch

## License

RepoLume is licensed under the [MIT License](LICENSE).
