"use client";

import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";

import { parseRepositoryAnswer } from "@/app/lib/answer-contract";
import type { RepositoryAnswerResult } from "@/app/lib/answer-contract";
import type { EvidenceMatch } from "@/app/lib/evidence-contract";
import { SAMPLE_REPOSITORIES } from "@/app/lib/sample-repositories";

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
  const [result, setResult] = useState<RepositoryAnswerResult | null>(null);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestController = useRef<AbortController | null>(null);
  const suggestedQuestion = SAMPLE_REPOSITORIES.find((sample) => sample.analysisId === analysisId)?.suggestedQuestion;

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
    setResult(null);

    try {
      const response = await fetch(`/api/analyses/${analysisId}/answer`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ question: normalizedQuestion, limit: 5 }),
        signal: controller.signal,
      });
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        setError(errorMessage(payload) ?? "RepoLume could not answer this question.");
        return;
      }
      const answerResult = parseRepositoryAnswer(payload);
      if (!answerResult) {
        setError("RepoLume received an invalid answer response.");
        return;
      }
      setResult(answerResult);
    } catch {
      if (!controller.signal.aborted) {
        setError("RepoLume could not reach the answer service.");
      }
    } finally {
      if (!controller.signal.aborted) setSearching(false);
    }
  }

  return (
    <section className="question-section" aria-labelledby="repository-question-heading">
      <div className="question-intro">
        <span className="section-label">GO ONE LEVEL DEEPER</span>
        <h2 id="repository-question-heading">Ask your codebase.</h2>
        <p>
          Trace a feature back to the files behind it. Every supported answer includes source references.
        </p>
        <span className="retrieval-note">Based on static source evidence</span>
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
              {searching ? "Tracing evidence…" : "Ask RepoLume"}
            </button>
          </div>
        </form>
        {suggestedQuestion ? <button className="suggested-question" type="button" onClick={() => { setQuestion(suggestedQuestion); document.getElementById("repository-question")?.focus(); }}>Try asking: {suggestedQuestion} <span aria-hidden="true">↗</span></button> : null}

        <div className="evidence-results" aria-live="polite">
          {error ? (
            <p className="analysis-notice" role="alert">
              {error}
            </p>
          ) : null}
          {searching ? <p className="empty-evidence">Tracing architecture evidence…</p> : null}
          {result && !error && !searching ? (
            <>
              <div className="evidence-result-heading">
                <span>Answer for</span>
                <strong>“{result.question}”</strong>
              </div>
              <div className={`grounded-answer grounding-${result.groundingStatus}`}>
                <span>
                  {result.groundingStatus === "supported"
                    ? "Source evidence found"
                    : "Not enough evidence"}
                </span>
                <p>{result.answer}</p>
              </div>
              {result.citations.length > 0 ? (
                <div className="citation-list">
                  <h3>Sources used</h3>
                  <ol>
                    {result.citations.map((match, index) => (
                      <li key={match.nodeId}>
                        <div>
                          <span>[{index + 1}] · {match.kind.replaceAll("_", " ")}</span>
                          <strong>{match.name}</strong>
                        </div>
                        <code>{locationLabel(match)}</code>
                        <p>
                          Matched {match.matchedTerms.join(", ")} · {match.relationshipCount}{" "}
                          {match.relationshipCount === 1 ? "relationship" : "relationships"}{" "}
                          · {match.confidence}
                        </p>
                      </li>
                    ))}
                  </ol>
                </div>
              ) : (
                <p className="empty-evidence">No source citations were attached to this answer.</p>
              )}
            </>
          ) : null}
          {!result && !error && !searching ? (
            <p className="empty-evidence">Your answer and source citations will appear here.</p>
          ) : null}
        </div>
      </div>
    </section>
  );
}
