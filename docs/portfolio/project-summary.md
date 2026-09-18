# RepoLume portfolio copy

Use these descriptions as a starting point and adjust them to match the space
available. They describe the current project without claiming roadmap features
are already finished.

## One-line description

RepoLume is a developer tool that turns public GitHub repositories into
interactive architecture maps and answers codebase questions with file and line
citations.

## Résumé bullets

- Built a full-stack architecture explorer with React, TypeScript, FastAPI,
  PostgreSQL, Redis Streams, Python AST, and Tree-sitter to map Python and
  TypeScript/JavaScript repositories into source-linked dependency graphs.
- Designed a durable background-analysis pipeline with bounded GitHub archive
  retrieval, at-least-once queue processing, persisted artifacts, and 339
  automated and live integration checks across the web, API, and worker.
- Deployed a sample-first public demo to Cloudflare Workers and added
  evidence-grounded repository questions, browser security headers, CI audits,
  and reproducible deployment smoke tests.

## Portfolio description

RepoLume helps developers understand an unfamiliar codebase before changing
it. It analyzes Python, TypeScript, and JavaScript projects, builds an
interactive architecture graph, and connects repository questions to exact
files and line ranges. I built it as a three-application monorepo with a React
web interface, FastAPI service, PostgreSQL storage, Redis job delivery, and a
Python analysis worker. The public demo uses deterministic samples so reviewers
can explore the complete interaction without waiting for infrastructure.

## 30-second interview answer

“I built RepoLume because file trees do not explain how a codebase fits
together. A user submits a public GitHub repository, the API creates a durable
job, and a Python worker parses the code with AST and Tree-sitter. The result is
stored as an architecture artifact and shown as an interactive React Flow
graph. Questions are answered from ranked source evidence, so the interface can
show the exact files and lines behind a claim. The public demo uses samples,
while the complete real-repository flow is verified locally.”

## Strong technical talking points

- Why the API records work before publishing to Redis
- How pending Redis Stream messages are recovered after interruption
- Why repository archives are analyzed without executing their code
- How confirmed and heuristic relationships are represented differently
- Why evidence retrieval was implemented before model-generated answers
- Why the public demo is sample-first instead of pretending the backend is live

## Honest boundaries

Do not describe the current answer engine as an LLM chat system. It is an
evidence-grounded static-analysis summary. Do not claim security scanning,
technical-debt scoring, pull-request review, or a hosted analysis backend as
finished features; those remain on the roadmap.
