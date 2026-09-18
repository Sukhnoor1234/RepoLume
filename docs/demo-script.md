# RepoLume demo video script

This is the short version to use in a portfolio video, README walkthrough, or
internship conversation.

Live demo: <https://repolume-web.sukhnoor-repolume.workers.dev>

## Before recording

- Use a 1080p browser window at 100% zoom.
- Close unrelated tabs, notifications, bookmarks, and personal account menus.
- Open the live demo and refresh it before recording.
- Keep the cursor still while speaking, then move deliberately.
- Record one clean 60–75 second take before trying extra edits.

## 60-second walkthrough

| Time | Screen action | Voiceover |
| --- | --- | --- |
| 0–7s | Show the landing page and headline. | “RepoLume helps developers understand a codebase before they start changing it.” |
| 7–16s | Point to public demo mode and select **Commerce platform**. | “The public demo uses built-in repositories, so anyone can try the full interaction without an account or a running backend.” |
| 16–30s | Fit the graph and select `POST /orders`, `createOrder`, and Redis. | “RepoLume turns source analysis into an interactive architecture map with modules, entry points, symbols, dependencies, and confidence-labelled relationships.” |
| 30–42s | Show the selected node’s source path and line range. | “Each useful node stays connected to its source location instead of becoming an unexplained diagram.” |
| 42–55s | Ask **How does an order get created?** | “Repository questions are answered from ranked static-analysis evidence.” |
| 55–67s | Hold on the answer and two citations. | “The answer cites the exact files and lines behind the claim, so a developer can verify it instead of trusting a guess.” |
| 67–72s | Return to the graph or headline. | “The complete system also includes FastAPI, PostgreSQL, Redis, and a background analysis worker.” |

## Short caption

RepoLume turns unfamiliar repositories into interactive architecture maps and
source-cited answers. Built with React, TypeScript, FastAPI, PostgreSQL, Redis,
Python AST, and Tree-sitter.

## What to be honest about

- The sample repositories are built-in so the demo is reliable.
- Live repository submission exists, but needs the API and worker services
  configured.
- Model-generated explanations and deployment polish are still in progress.

## Best talking points

- Full-stack project with a Next.js web app, FastAPI service, and Python worker.
- Static analysis pipeline for TypeScript, JavaScript, and Python repositories.
- Evidence-first answers so the app can cite files instead of guessing.
- Milestone-based development with tests and pull requests for each checkpoint.
