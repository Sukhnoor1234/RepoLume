import { RepositoryAnalyzer } from "@/app/components/repository-analyzer";

const architectureNodes = [
  { label: "Frontend", type: "Interface", className: "node-frontend" },
  { label: "API Gateway", type: "Entry point", className: "node-gateway" },
  { label: "Auth Service", type: "Service", className: "node-auth" },
  { label: "Order Service", type: "Service", className: "node-orders" },
  { label: "PostgreSQL", type: "Database", className: "node-postgres" },
  { label: "Redis", type: "Cache", className: "node-redis" },
] as const;

export default function Home() {
  return (
    <main>
      <nav className="site-nav" aria-label="Primary navigation">
        <a className="brand" href="#" aria-label="RepoLume home">
          <span className="brand-mark" aria-hidden="true">RL</span>
          <span>RepoLume</span>
        </a>
        <div className="nav-links">
          <a href="#how-it-works">How it works</a>
          <a href="#roadmap">Roadmap</a>
          <a className="github-link" href="https://github.com/Sukhnoor1234/RepoLume" target="_blank" rel="noreferrer">
            GitHub
          </a>
        </div>
      </nav>

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

          <RepositoryAnalyzer />

          <div className="hero-details" aria-label="Initial product scope">
            <span>TypeScript</span>
            <span>Python</span>
            <span>Source-linked answers</span>
          </div>
        </div>

        <div className="architecture-card" aria-label="Example architecture map">
          <div className="map-header">
            <div>
              <span className="map-kicker">Architecture preview</span>
              <h2>commerce-platform</h2>
            </div>
            <span className="analysis-status">Sample map</span>
          </div>

          <div className="architecture-map">
            <div className="map-grid" aria-hidden="true" />
            <div className="map-line line-main" aria-hidden="true" />
            <div className="map-line line-branch" aria-hidden="true" />
            {architectureNodes.map((node) => (
              <div className={`map-node ${node.className}`} key={node.label}>
                <span className="node-type">{node.type}</span>
                <strong>{node.label}</strong>
              </div>
            ))}
          </div>

          <div className="map-footer">
            <span><i className="legend-dot confirmed" aria-hidden="true" />Confirmed relationship</span>
            <span><i className="legend-dot inferred" aria-hidden="true" />Inferred relationship</span>
          </div>
        </div>
      </section>

      <section className="principles" id="how-it-works">
        <article>
          <span>01</span>
          <h2>Map the structure</h2>
          <p>Find modules, services, entry points, data stores, and dependencies.</p>
        </article>
        <article>
          <span>02</span>
          <h2>Follow the evidence</h2>
          <p>Inspect supported relationships through their source locations.</p>
        </article>
        <article id="roadmap">
          <span>03</span>
          <h2>Ask better questions</h2>
          <p>Explore behavior, request paths, and change impact with cited answers.</p>
        </article>
      </section>
    </main>
  );
}
