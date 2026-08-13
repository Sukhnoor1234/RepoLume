# RepoLume Web

This directory contains the RepoLume web application.

## Current milestone

The current version includes the responsive product foundation and the first
complete repository-analysis interaction. Visitors can submit a public GitHub
URL, follow its durable analysis status, and explore a completed architecture
artifact as an interactive, source-linked dependency graph.

## Commands

- `npm run dev` starts local development.
- `npm run build` creates the production worker build.
- `npm run lint` checks the source with ESLint.
- `npm test` builds the application and verifies the rendered HTML.

## Configuration

Set `REPOLUME_API_URL` on the web server to the FastAPI origin. For local
development this is usually `http://127.0.0.1:8000`. The value remains
server-side and is never included in the browser bundle.

Without this setting, analysis requests fail closed with a safe service
unavailable message. The transport boundary is documented in
[web analysis submission](../../docs/web/analysis-submission.md), and the graph
experience is documented in
[architecture explorer](../../docs/web/architecture-explorer.md).
