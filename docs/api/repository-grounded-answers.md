# Repository grounded answers

- **Status:** Implemented
- **Checkpoint:** 18
- **Contract version:** 1.0

RepoLume can compose a short repository answer after an analysis completes.
The answer route retrieves the same ranked architecture evidence as the
diagnostic evidence endpoint and cites at most the first three source matches.

## Contract

`POST /v1/analyses/{analysis_id}/answer`

```json
{
  "question": "Where is order creation implemented?",
  "limit": 5
}
```

A supported response contains `grounding_status: "supported"`, answer text
with `[1]` citation markers, and matching citation records. Each citation keeps
the node kind, name, language, repository-relative path and line range,
confidence, ranking score, matched terms, and relationship count.

If retrieval returns no matches, the route responds successfully with
`grounding_status: "insufficient_evidence"` and no citations. It recommends a
more specific question instead of inventing an implementation.

## Safety boundary

The Checkpoint 18 composer is deterministic. It summarizes static-analysis
matches and always reminds the user to inspect cited lines before relying on a
runtime claim. It does not read source contents during the request, execute
repository code, call an external model, persist questions, or create chat
history.

Source-chunk retrieval, semantic embeddings, an LLM provider adapter, answer
evaluation, and multi-turn conversation remain later checkpoints.
