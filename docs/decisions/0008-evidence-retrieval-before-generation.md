# ADR 0008: Establish explainable evidence retrieval before answer generation

- **Status:** Accepted
- **Date:** 2026-08-26

## Context

Repository chat needs trustworthy context before it can generate useful
answers. Adding an LLM directly to the completed architecture would make it
difficult to distinguish retrieval failures from generation failures and could
encourage unsupported answers.

## Decision

Checkpoint 17 introduces a deterministic lexical retriever over the validated
architecture artifact. The API returns ranked, source-located nodes and the
terms that caused each match. The web interface displays those results as
evidence and clearly states that it has not generated an answer.

The retriever is stateless, bounded to ten results, and uses stable tie-breaks.
It does not read repository files during the request, create embeddings, call
an external model, or persist questions.

## Consequences

- Retrieval behavior can be unit tested independently of an AI provider.
- Users can inspect the evidence and its limitations immediately.
- Later RAG work has a stable response contract and evaluation baseline.
- Lexical ranking will miss some semantic matches until source chunks,
  embeddings, and reranking are added.
- Generated repository answers and conversation persistence remain separate
  decisions.
