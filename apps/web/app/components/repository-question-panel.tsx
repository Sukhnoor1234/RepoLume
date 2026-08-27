"use client";

import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";

import { parseEvidenceQueryResult } from "@/app/lib/evidence-contract";
import type { EvidenceMatch } from "@/app/lib/evidence-contract";

type ErrorEnvelope = { error: { message: string } };

function errorMessage(value: unknown): string | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return null;
  const error = (value as { error?: unknown }).error;
  if (typeof error !== "object" || error === null || Array.isArray(error)) return null;
  const message = (error as ErrorEnvelope["error"]).message;
  return typeof message === "string" ? message : null;
}

function locationLabel(match: EvidenceMatch) {
  const { path, line, endLine } = match.location;
  return `${path}:${line}${endLine === line ? "" : `–${endLine}`}`;
}

export function RepositoryQuestionPanel({ analysisId }: { analysisId: string }) {
  const [question, setQuestion] = useState("");
  const [askedQuestion, setAskedQuestion] = useState<string | null>(null);
  const [matches, setMatches] = useState<EvidenceMatch[]>([]);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestController = useRef<AbortController | null>(null);

  useEffect(() => () => requestController.current?.abort(), []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedQuestion = question.trim();
    if (normalizedQuestion.length < 3) return;

    requestController.current?.abort();
    const controller = new AbortController();
    requestController.current = controller;
    setSearching(true);
    setError(null);
    setAskedQuestion(null);
    setMatches([]);

    try {
      const response = await fetch(`/api/analyses/${analysisId}/evidence-query`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ question: normalizedQuestion, limit: 5 }),
        signal: controller.signal,
      });
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        setError(errorMessage(payload) ?? "RepoLume could not search this architecture.");
        return;
      }
      const result = parseEvidenceQueryResult(payload);
      if (!result) {
        setError("RepoLume received an invalid evidence response.");
        return;
      }
      setAskedQuestion(result.question);
      setMatches(result.matches);
    } catch {
      if (!controller.signal.aborted) {
        setError("RepoLume could not reach the evidence service.");
      }
    } finally {
      if (!controller.signal.aborted) setSearching(false);
    }
  }

  return (
    <section className="question-section" aria-labelledby="repository-question-heading">
      <div className="question-intro">
        <span className="map-kicker">Repository questions</span>
        <h2 id="repository-question-heading">Find the source before generating an answer.</h2>
        <p>
          Ask where something is implemented. RepoLume ranks evidence from the completed
          architecture and shows exactly why each file matched.
        </p>
        <span className="retrieval-note">Evidence search · No generated answer yet</span>
      </div>

      <div className="question-workspace">
        <form className="question-form" onSubmit={submit}>
          <label htmlFor="repository-question">Question about this repository</label>
          <div>
            <input
              id="repository-question"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Where is user authentication implemented?"
              minLength={3}
              maxLength={300}
              required
            />
            <button type="submit" disabled={searching || question.trim().length < 3}>
              {searching ? "Searching…" : "Find evidence"}
            </button>
          </div>
        </form>

        <div className="evidence-results" aria-live="polite">
          {error ? <p className="analysis-notice" role="alert">{error}</p> : null}
          {searching ? <p className="empty-evidence">Searching architecture evidence…</p> : null}
          {askedQuestion && !error && !searching ? (
            <>
              <div className="evidence-result-heading">
                <span>Evidence for</span>
                <strong>“{askedQuestion}”</strong>
              </div>
              {matches.length > 0 ? (
                <ol>
                  {matches.map((match) => (
                    <li key={match.nodeId}>
                      <div>
                        <span>{match.kind.replaceAll("_", " ")}</span>
                        <strong>{match.name}</strong>
                      </div>
                      <code>{locationLabel(match)}</code>
                      <p>
                        Matched {match.matchedTerms.join(", ")} · {match.relationshipCount}{" "}
                        {match.relationshipCount === 1 ? "relationship" : "relationships"} · {match.confidence}
                      </p>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="empty-evidence">No source-backed matches were found for this question.</p>
              )}
            </>
          ) : null}
          {!askedQuestion && !error && !searching ? (
            <p className="empty-evidence">Your ranked source matches will appear here.</p>
          ) : null}
        </div>
      </div>
    </section>
  );
}
