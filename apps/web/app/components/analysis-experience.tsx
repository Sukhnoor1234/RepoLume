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

type AnalysisExperienceProps = {
  liveAnalysisEnabled: boolean;
};

export function AnalysisExperience({ liveAnalysisEnabled }: AnalysisExperienceProps) {
  const [display, setDisplay] = useState<ArchitectureDisplayState>(EMPTY_ARCHITECTURE);
  const updateDisplay = useCallback((next: ArchitectureDisplayState) => setDisplay(next), []);

  return (
    <>
      <section className="workspace-intro">
        <div>
          <span className="section-label">THE BIG PICTURE, IN FOCUS</span>
          <h1>Get to know your codebase<span>.</span></h1>
          <p className="hero-description">
            Explore the structure. Follow the connections. Find where things happen.
          </p>
        </div>
        <span className="intro-note">Less searching.<br />More understanding.</span>
      </section>
      <section className="exploration-workspace" aria-label="Repository workspace">
        <RepositoryAnalyzer
          liveAnalysisEnabled={liveAnalysisEnabled}
          onArchitectureChange={updateDisplay}
        />

        <ArchitecturePanel display={display} />
      </section>
      {display.analysisId && display.architecture ? (
        <RepositoryQuestionPanel analysisId={display.analysisId} key={display.analysisId} />
      ) : null}
    </>
  );
}
