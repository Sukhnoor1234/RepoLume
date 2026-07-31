# RepoLume

> Understand any codebase before you touch it.

RepoLume is an **AI architecture explorer** that transforms a public GitHub
repository into an interactive software architecture map. It is designed to
help developers understand unfamiliar systems, trace how features work, and
ask questions that are answered with evidence from the source code.

## Project status

RepoLume is under active development. The repository currently contains the
project foundation, architecture decisions, the first web interface, and the
initial HTTP API. The repository-analysis features are not yet available.

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
5. Trace supported request flows and estimate the impact of changing or
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
| Analysis | Tree-sitter with language-specific resolvers |
| Data | PostgreSQL, pgvector, Redis |
| AI | Retrieval-augmented generation, embeddings, LLM provider adapter |
| Delivery | Docker, GitHub Actions, managed cloud services |

Technology choices may be refined through documented architecture decisions as
the product develops.

## Planned repository structure

RepoLume will use a monorepo containing independently deployable web, API, and
analysis-worker applications. The decision and its tradeoffs are recorded in
[ADR 0001](docs/decisions/0001-monorepo-architecture.md).

## Run the web application

The current web foundation lives in `apps/web`.

```bash
cd apps/web
npm install
npm run dev
```

The repository input is intentionally disabled until the ingestion milestone.

## Run the API

The API foundation lives in `apps/api` and requires Python 3.12.

```bash
cd apps/api
python -m venv .venv
python -m pip install -e ".[dev]"
python -m uvicorn repolume_api.main:app --reload
```

The current API exposes only service health and generated documentation.

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
