# RepoLume Web

This directory contains the RepoLume web application.

## Current milestone

The current version includes the responsive product foundation and the first
complete repository-analysis interaction. Visitors can submit a public GitHub
URL, follow its durable analysis status, and explore a completed architecture
artifact as an interactive, source-linked dependency graph. After completion,
visitors can ask a repository question and inspect deterministic source matches
inside a concise answer with numbered file and line citations. The current
answer is a conservative static-analysis summary; model generation and chat
history remain later work.

The web app also includes sample repositories that load through the same local
architecture and answer contracts. They make the demo usable even when the
live FastAPI runtime is not configured.

## Commands

- `npm run dev` starts local development.
- `npm run build` creates the production worker build.
- `npm run lint` checks the source with ESLint.
- `npm test` builds the application and verifies the rendered HTML.

## Configuration

Copy `.dev.vars.example` to `.dev.vars` for local development. The example sets
`REPOLUME_API_URL` to `http://localhost:8000`, and Vinext exposes that binding
only to the local server runtime. The real `.dev.vars` file is ignored so
future secrets cannot be committed accidentally.

Without this setting, analysis requests fail closed with a safe service
unavailable message. The transport boundary is documented in
[web analysis submission](../../docs/web/analysis-submission.md), and the graph
experience is documented in
[architecture explorer](../../docs/web/architecture-explorer.md). The question
workflow is documented in
[repository evidence search](../../docs/web/repository-evidence-search.md) and
[grounded repository answers](../../docs/web/repository-answers.md).
The no-wait sample flow is documented in
[sample repositories](../../docs/web/sample-repositories.md).
