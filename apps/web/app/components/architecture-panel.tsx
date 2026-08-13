"use client";

import dynamic from "next/dynamic";

import type { ArchitectureDisplayState } from "@/app/components/repository-analyzer";

const InteractiveArchitecture = dynamic(
  () => import("@/app/components/architecture-explorer"),
  {
    ssr: false,
    loading: () => <div className="map-message">Preparing the interactive graph…</div>,
  },
);

const sampleNodes = [
  { label: "Frontend", type: "Interface", className: "node-frontend" },
  { label: "API Gateway", type: "Entry point", className: "node-gateway" },
  { label: "Auth Service", type: "Service", className: "node-auth" },
  { label: "Order Service", type: "Service", className: "node-orders" },
  { label: "PostgreSQL", type: "Database", className: "node-postgres" },
  { label: "Redis", type: "Cache", className: "node-redis" },
] as const;

export function ArchitecturePanel({ display }: { display: ArchitectureDisplayState }) {
  if (display.architecture && display.analysisId) {
    return (
      <div className="architecture-card architecture-card-live" aria-label="Repository architecture explorer">
        <InteractiveArchitecture
          key={display.analysisId}
          architecture={display.architecture}
        />
      </div>
    );
  }

  return (
    <div className="architecture-card" aria-label="Example architecture map">
      <div className="map-header">
        <div>
          <span className="map-kicker">Architecture preview</span>
          <h2>commerce-platform</h2>
        </div>
        <span className="analysis-status">Sample map</span>
      </div>

      {display.loading ? <div className="map-message">Loading the completed architecture…</div> : null}
      {display.error ? <div className="map-message map-message-error">{display.error}</div> : null}
      {!display.loading && !display.error ? (
        <div className="architecture-map">
          <div className="map-grid" aria-hidden="true" />
          <div className="map-line line-main" aria-hidden="true" />
          <div className="map-line line-branch" aria-hidden="true" />
          {sampleNodes.map((node) => (
            <div className={`map-node ${node.className}`} key={node.label}>
              <span className="node-type">{node.type}</span>
              <strong>{node.label}</strong>
            </div>
          ))}
        </div>
      ) : null}

      <div className="map-footer">
        <span><i className="legend-dot confirmed" aria-hidden="true" />Confirmed relationship</span>
        <span><i className="legend-dot inferred" aria-hidden="true" />Inferred relationship</span>
      </div>
    </div>
  );
}
