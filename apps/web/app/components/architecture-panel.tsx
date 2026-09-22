"use client";

import dynamic from "next/dynamic";
import { Icon } from "@/app/components/brand";
import type { ArchitectureDisplayState } from "@/app/components/repository-analyzer";

const InteractiveArchitecture = dynamic(
  () => import("@/app/components/architecture-explorer"),
  { ssr: false, loading: () => <div className="map-message" role="status">Preparing the interactive graph…</div> },
);

export function ArchitecturePanel({ display }: { display: ArchitectureDisplayState }) {
  if (display.architecture && display.analysisId) {
    return <div className="architecture-card architecture-card-live" aria-label="Repository architecture explorer"><InteractiveArchitecture key={display.analysisId} architecture={display.architecture} /></div>;
  }
  return (
    <div className="architecture-card" aria-label="Example architecture map">
      <div className="map-header"><div className="map-title"><Icon name="map" /><h2>Architecture map</h2></div><span className="analysis-status">Illustrative preview</span></div>
      {display.loading ? <div className="map-message" role="status">Loading the completed architecture…</div> : null}
      {display.error ? <div className="map-message map-message-error" role="alert">{display.error}</div> : null}
      {!display.loading && !display.error ? (
        <div className="architecture-preview">
          <div className="preview-copy"><span className="section-label">EVERY CONNECTION TELLS A STORY</span><h3>A file tree shows the pieces.<br />See how they fit together.</h3><p>Choose a repository above to open its interactive map and inspect the source behind each connection.</p><span className="preview-hint"><span className="hint-line" />Your exploration starts here</span></div>
          <div className="preview-diagram" role="img" aria-label="Illustrative architecture with an orders route, an order service, and a Redis cache.">
            <svg className="preview-connections" viewBox="0 0 440 290" aria-hidden="true"><path d="M100 70V135H220V177M220 135H357V177" /><path d="M220 232v25" strokeDasharray="4 4" /></svg>
            <div className="preview-node preview-route"><span><i />ENTRY POINT</span><strong>POST /orders</strong><code>routes/orders.ts</code></div>
            <div className="preview-node preview-service"><span><i />SERVICE</span><strong>createOrder()</strong><code>services/orders.ts</code></div>
            <div className="preview-node preview-cache"><span><i />DEPENDENCY</span><strong>Redis</strong><code>Cache</code></div>
            <span className="preview-annotation">follow the source</span>
          </div>
        </div>
      ) : null}
      <div className="map-footer"><span><i className="legend-dot confirmed" />Source-linked nodes</span><span><i className="legend-dot inferred" />Labelled relationships</span><span className="map-footer-note">Python · TypeScript · JavaScript</span></div>
    </div>
  );
}
