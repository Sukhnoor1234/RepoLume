# ADR 0009: Add grounded summaries before model generation

- **Status:** Accepted
- **Date:** 2026-08-27

## Context

Checkpoint 17 established deterministic evidence retrieval, but a repository
question still returned only a list of matches. RepoLume needs an answer-shaped
experience without weakening the rule that every claim must remain inspectable.
Adding a model provider before source chunks and answer evaluation would make
unsupported output difficult to detect.

## Decision

Checkpoint 18 adds a deterministic answer composer over the ranked evidence.
It cites at most three source locations, limits its language to what the
architecture artifact supports, and declines to answer when retrieval is empty.
The evidence endpoint remains available independently for testing and debugging.

The browser renders answer text as plain content and shows each citation with
its path, line range, match reason, relationship count, and confidence.

## Consequences

- The complete question-to-citation interaction can be tested without secrets,
  network cost, or model nondeterminism.
- Empty retrieval produces an explicit insufficient-evidence result.
- The answer is intentionally a static-analysis summary, not an AI-generated
  explanation of runtime behavior.
- A future model adapter can consume the same citation contract after source
  chunks and evaluation guardrails are available.
