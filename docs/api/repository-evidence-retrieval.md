# Repository evidence retrieval

- **Status:** Implemented
- **Checkpoint:** 17
- **Contract version:** 1.0

RepoLume can retrieve source evidence for a natural-language question after an
analysis completes. This is the retrieval foundation for repository chat, not
an LLM answer endpoint.

## Ranking inputs

The retriever tokenizes the question and architecture fields, splits camelCase
and snake_case names, removes common question words, and normalizes
authentication terms to `auth`. It scores exact token matches across:

1. node name
2. qualified name and repository-relative source path
3. node detail and decorators
4. language, node kind, and symbol kind

Only modules, symbols, and entry points with source locations are eligible.
Results are ordered by score, matched-term coverage, path, line, and stable node
ID. The same artifact and question therefore produce the same result order.

## Response evidence

Each match includes its stable node ID, kind, name, language, path and line
range, confidence, numeric score, matched terms, and relationship count. No
source contents, secrets, model prompts, or generated claims are returned.

## Intentional limitations

Lexical matching cannot yet understand synonyms beyond the small documented
normalization rules, conceptual questions, call behavior, or semantic meaning.
Embeddings, source chunk retrieval, reranking, LLM answer generation,
citations inside generated prose, chat history, and evaluation datasets remain
later checkpoints.
