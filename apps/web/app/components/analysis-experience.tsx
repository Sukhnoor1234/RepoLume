"use client";

import { useCallback, useState } from "react";

import { ArchitecturePanel } from "@/app/components/architecture-panel";
import { RepositoryAnalyzer } from "@/app/components/repository-analyzer";
import { RepositoryQuestionPanel } from "@/app/components/repository-question-panel";
import type { ArchitectureDisplayState } from "@/app/components/repository-analyzer";

const EMPTY_ARCHITECTURE: ArchitectureDisplayState = {
  analysisId: null,
  architecture: null,
  loading: false,
  error: null,
};

export function AnalysisExperience() {
  const [display, setDisplay] = useState<ArchitectureDisplayState>(EMPTY_ARCHITECTURE);
  const updateDisplay = useCallback((next: ArchitectureDisplayState) => setDisplay(next), []);

  return (
    <>
      <section className="hero">
        <div className="hero-copy">
          <div className="eyebrow">
            <span className="status-dot" aria-hidden="true" />
            AI architecture explorer
          </div>
          <h1>Understand any codebase before you touch it.</h1>
          <p className="hero-description">
            RepoLume turns public repositories into interactive architecture maps,
            then helps you trace systems and ask questions with answers grounded
            in the source code.
          </p>

          <RepositoryAnalyzer onArchitectureChange={updateDisplay} />

          <div className="hero-details" aria-label="Initial product scope">
            <span>TypeScript</span>
            <span>Python</span>
            <span>Source-linked answers</span>
          </div>
        </div>

        <ArchitecturePanel display={display} />
      </section>
      {display.analysisId && display.architecture ? (
        <RepositoryQuestionPanel analysisId={display.analysisId} />
      ) : null}
    </>
  );
}
