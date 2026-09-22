"use client";

import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Icon } from "@/app/components/brand";

import { parseArchitecture } from "@/app/lib/architecture-contract";
import type { RepositoryArchitecture } from "@/app/lib/architecture-contract";
import { SAMPLE_REPOSITORIES } from "@/app/lib/sample-repositories";
import type { SampleRepository } from "@/app/lib/sample-repositories";

type AnalysisStatus = "queued" | "cloning" | "analyzing" | "completed" | "failed";

type AnalysisState = {
  analysisId: string;
  status: AnalysisStatus;
  resultAvailable: boolean;
  failure: { code: string; message: string } | null;
};

type ErrorEnvelope = { error: { code: string; message: string } };

export type ArchitectureDisplayState = {
  analysisId: string | null;
  architecture: RepositoryArchitecture | null;
  loading: boolean;
  error: string | null;
};

type RepositoryAnalyzerProps = {
  liveAnalysisEnabled: boolean;
  onArchitectureChange: (state: ArchitectureDisplayState) => void;
};

const STATUS_LABELS: Record<AnalysisStatus, string> = {
  queued: "Waiting for a worker",
  cloning: "Retrieving repository",
  analyzing: "Mapping source code",
  completed: "Architecture ready",
  failed: "Analysis stopped",
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseError(value: unknown): ErrorEnvelope | null {
  if (!isRecord(value) || !isRecord(value.error)) return null;
  if (typeof value.error.code !== "string" || typeof value.error.message !== "string") return null;
  return { error: { code: value.error.code, message: value.error.message } };
}

function parseStatus(value: unknown): AnalysisState | null {
  if (!isRecord(value)) return null;
  const statuses: AnalysisStatus[] = ["queued", "cloning", "analyzing", "completed", "failed"];
  if (
    typeof value.analysis_id !== "string" ||
    typeof value.status !== "string" ||
    !statuses.includes(value.status as AnalysisStatus) ||
    typeof value.result_available !== "boolean"
  ) {
    return null;
  }
  let failure: AnalysisState["failure"] = null;
  if (value.failure !== null) {
    if (
      !isRecord(value.failure) ||
      typeof value.failure.code !== "string" ||
      typeof value.failure.message !== "string"
    ) {
      return null;
    }
    failure = { code: value.failure.code, message: value.failure.message };
  }
  return {
    analysisId: value.analysis_id,
    status: value.status as AnalysisStatus,
    resultAvailable: value.result_available,
    failure,
  };
}

async function responsePayload(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

export function RepositoryAnalyzer({
  liveAnalysisEnabled,
  onArchitectureChange,
}: RepositoryAnalyzerProps) {
  const [repositoryUrl, setRepositoryUrl] = useState("");
  const [analysis, setAnalysis] = useState<AnalysisState | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const submissionController = useRef<AbortController | null>(null);
  const currentAnalysisId = analysis?.analysisId;
  const currentStatus = analysis?.status;
  const resultAvailable = analysis?.resultAvailable ?? false;

  useEffect(() => () => submissionController.current?.abort(), []);

  useEffect(() => {
    if (!currentAnalysisId || currentStatus === "completed" || currentStatus === "failed") return;
    const controller = new AbortController();

    async function poll() {
      while (!controller.signal.aborted) {
        await new Promise((resolve) => setTimeout(resolve, 1_500));
        if (controller.signal.aborted) return;
        try {
          const response = await fetch(`/api/analyses/${currentAnalysisId}`, {
            cache: "no-store",
            signal: controller.signal,
          });
          const payload = await responsePayload(response);
          if (!response.ok) {
            setNotice(
              parseError(payload)?.error.message ?? "RepoLume could not refresh this analysis.",
            );
            return;
          }
          const next = parseStatus(payload);
          if (!next) {
            setNotice("RepoLume received an unexpected analysis response.");
            return;
          }
          setAnalysis(next);
          setNotice(null);
          if (next.status === "completed" || next.status === "failed") return;
        } catch {
          if (!controller.signal.aborted) {
            setNotice("RepoLume could not reach the analysis service.");
          }
          return;
        }
      }
    }

    void poll();
    return () => controller.abort();
  }, [currentAnalysisId, currentStatus]);

  useEffect(() => {
    if (!currentAnalysisId || currentStatus !== "completed" || !resultAvailable) return;
    const controller = new AbortController();
    onArchitectureChange({
      analysisId: currentAnalysisId,
      architecture: null,
      loading: true,
      error: null,
    });

    async function loadArchitecture(analysisId: string) {
      try {
        const response = await fetch(`/api/analyses/${analysisId}/architecture`, {
          cache: "no-store",
          signal: controller.signal,
        });
        const payload = await responsePayload(response);
        if (!response.ok) {
          onArchitectureChange({
            analysisId,
            architecture: null,
            loading: false,
            error:
              parseError(payload)?.error.message ??
              "RepoLume could not load the completed architecture.",
          });
          return;
        }
        const architecture = parseArchitecture(payload);
        if (!architecture) {
          onArchitectureChange({
            analysisId,
            architecture: null,
            loading: false,
            error: "RepoLume received an invalid architecture response.",
          });
          return;
        }
        onArchitectureChange({
          analysisId,
          architecture,
          loading: false,
          error: null,
        });
      } catch {
        if (!controller.signal.aborted) {
          onArchitectureChange({
            analysisId,
            architecture: null,
            loading: false,
            error: "RepoLume could not reach the architecture service.",
          });
        }
      }
    }

    void loadArchitecture(currentAnalysisId);
    return () => controller.abort();
  }, [currentAnalysisId, currentStatus, onArchitectureChange, resultAvailable]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!liveAnalysisEnabled) return;
    const formData = new FormData(event.currentTarget);
    const submittedRepositoryUrl = String(formData.get("repository-url") ?? "").trim();
    submissionController.current?.abort();
    const controller = new AbortController();
    submissionController.current = controller;
    setSubmitting(true);
    setAnalysis(null);
    setNotice(null);
    onArchitectureChange({
      analysisId: null,
      architecture: null,
      loading: false,
      error: null,
    });

    try {
      const response = await fetch("/api/analyses", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ repository_url: submittedRepositoryUrl }),
        signal: controller.signal,
      });
      const payload = await responsePayload(response);
      if (!response.ok) {
        setNotice(
          parseError(payload)?.error.message ?? "RepoLume could not start this analysis.",
        );
        return;
      }
      if (
        !isRecord(payload) ||
        typeof payload.analysis_id !== "string" ||
        payload.status !== "queued"
      ) {
        setNotice("RepoLume received an unexpected submission response.");
        return;
      }
      setAnalysis({
        analysisId: payload.analysis_id,
        status: "queued",
        resultAvailable: false,
        failure: null,
      });
    } catch {
      if (!controller.signal.aborted) {
        setNotice("RepoLume could not reach the analysis service.");
      }
    } finally {
      if (!controller.signal.aborted) setSubmitting(false);
    }
  }

  function loadSample(sample: SampleRepository) {
    submissionController.current?.abort();
    setRepositoryUrl("");
    setSubmitting(false);
    setNotice(null);
    setAnalysis({
      analysisId: sample.analysisId,
      status: "completed",
      resultAvailable: true,
      failure: null,
    });
  }

  return (
    <div className="repository-preview" aria-label="Repository analyzer">
      <div className="repository-section-heading">
        <div><span className="section-label">01 / CHOOSE YOUR STARTING POINT</span><h2>Explore a repository</h2></div>
        <span className="sample-access-note">No account needed</span>
      </div>
      <div className="sample-repositories" aria-label="Sample repositories">
        <div>
          {SAMPLE_REPOSITORIES.map((sample) => (
            <button key={sample.analysisId} type="button" aria-pressed={currentAnalysisId === sample.analysisId} onClick={() => loadSample(sample)}>
              <span className={`sample-icon language-${sample.language.toLowerCase()}`}><Icon name="folder" /></span>
              <span className="sample-copy">
                <span className="sample-title"><strong>{sample.name}</strong><small>{sample.language}</small></span>
                <span className="sample-description">{sample.description}</span>
                <span className="sample-question">{sample.suggestedQuestion}</span>
              </span>
              <Icon name="arrow" />
            </button>
          ))}
        </div>
      </div>
      <details className="repository-import" open={liveAnalysisEnabled ? true : undefined}>
        <summary><Icon name="code" />Bring your own repository<span>{liveAnalysisEnabled ? "Available" : "Local setup required"}</span></summary>
        {!liveAnalysisEnabled ? <p className="demo-mode-note">The public demo uses curated examples. To analyse your own repository, <a href="https://github.com/Sukhnoor1234/RepoLume#run-it-locally" target="_blank" rel="noreferrer">run RepoLume locally <Icon name="external" /></a>.</p> : null}
        <form onSubmit={submit}>
        <label htmlFor="repository-url">Public GitHub repository</label>
        <div className="repository-controls">
          <input
            id="repository-url"
            name="repository-url"
            type="url"
            placeholder="https://github.com/owner/repository"
            value={repositoryUrl}
            onChange={(event) => setRepositoryUrl(event.target.value)}
            required={liveAnalysisEnabled}
            disabled={!liveAnalysisEnabled}
            maxLength={2048}
            autoComplete="url"
            aria-describedby="repository-note repository-feedback"
          />
          <button type="submit" disabled={submitting || !liveAnalysisEnabled}>
            {submitting
              ? "Starting…"
              : liveAnalysisEnabled
                ? "Analyze repository"
                : "Available locally"}
          </button>
        </div>
        <p id="repository-note">
          {liveAnalysisEnabled
            ? "Public GitHub repositories only. Analysis runs asynchronously."
            : "The hosted demo uses built-in samples. The full repository flow is verified locally."}
        </p>
      </form>
      </details>

      <div id="repository-feedback" className="analysis-feedback" aria-live="polite">
        {analysis && analysis.status !== "completed" ? (
          <div className={`analysis-progress status-${analysis.status}`}>
            <div>
              <span className="analysis-progress-label">{STATUS_LABELS[analysis.status]}</span>
              <code>{analysis.analysisId}</code>
            </div>
            <span className="analysis-progress-status">{analysis.status}</span>
            {analysis.failure ? <p>{analysis.failure.message}</p> : null}
          </div>
        ) : null}
        {analysis?.status === "completed" ? <p className="sr-only">{analysis.resultAvailable ? "Architecture ready. Explore the map below." : "Analysis completed without an architecture result."}</p> : null}
        {notice ? <p className="analysis-notice" role="alert">{notice}</p> : null}
      </div>
    </div>
  );
}
