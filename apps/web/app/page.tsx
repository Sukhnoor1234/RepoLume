import { AnalysisExperience } from "@/app/components/analysis-experience";
import Link from "next/link";
import { Icon, Logo } from "@/app/components/brand";
import { isLiveAnalysisEnabled } from "@/app/lib/repolume-runtime";

export const dynamic = "force-dynamic";
const REPOSITORY = "https://github.com/Sukhnoor1234/RepoLume";

export default function Home() {
  const liveAnalysisEnabled = isLiveAnalysisEnabled();
  return (
    <div className="app-shell">
      <a className="skip-link" href="#workspace">Skip to workspace</a>
      <aside className="sidebar">
        <Link className="brand" href="/" aria-label="RepoLume home">
          <Logo />
          <span>RepoLume<span className="brand-period">.</span></span>
        </Link>
        <div className="sidebar-caption">YOUR CODE, CONNECTED</div>
        <nav className="primary-nav" aria-label="Primary navigation">
          <span className="nav-section-label">Workspace</span>
          <a href="#workspace" className="nav-active">
            <Icon name="map" />Explorer<span className="nav-indicator" />
          </a>
          <a href="#how-it-works"><Icon name="guide" />Quick guide</a>
          <span className="nav-section-label resources-label">Resources</span>
          <a href={`${REPOSITORY}/blob/main/docs/architecture.md`} target="_blank" rel="noreferrer">
            <Icon name="book" />Documentation<Icon name="external" />
          </a>
          <a href={`${REPOSITORY}#roadmap`} target="_blank" rel="noreferrer">
            <Icon name="route" />Roadmap<Icon name="external" />
          </a>
        </nav>
        <div className="sidebar-bottom">
          <p>Built to make unfamiliar<br />code feel familiar.</p>
          <a href={REPOSITORY} target="_blank" rel="noreferrer">
            <Icon name="code" />View source<Icon name="external" />
          </a>
          <span>OPEN SOURCE · MIT LICENSE</span>
        </div>
      </aside>
      <div className="main-shell">
        <header className="workspace-header">
          <div>
            <Icon name="map" /><span>Workspace</span>
            <span className="breadcrumb-divider">/</span><strong>Architecture explorer</strong>
          </div>
          <span className="environment-label">
            <i aria-hidden="true" />{liveAnalysisEnabled ? "Live analysis" : "Public demo"}
          </span>
        </header>
        <main id="workspace" tabIndex={-1}>
          <AnalysisExperience liveAnalysisEnabled={liveAnalysisEnabled} />
          <section className="quick-guide" id="how-it-works" aria-labelledby="guide-heading">
            <div className="guide-heading">
              <span className="section-label">A QUICK ORIENTATION</span>
              <h2 id="guide-heading">From repository to understanding.</h2>
            </div>
            <div className="guide-steps">
              <article>
                <span>01</span>
                <div><h3>Choose a repository</h3><p>Open a curated example to explore without signing in.</p></div>
              </article>
              <article>
                <span>02</span>
                <div><h3>Follow the connections</h3><p>Select a node to see its role, relationships, and source location.</p></div>
              </article>
              <article>
                <span>03</span>
                <div><h3>Ask a question</h3><p>Get an answer with file and line references you can inspect.</p></div>
              </article>
            </div>
          </section>
          <footer className="workspace-footer">
            <span>RepoLume <span className="footer-dot">/</span> Understand before you build.</span>
            <div className="footer-links">
              <a href={REPOSITORY} target="_blank" rel="noreferrer">GitHub <Icon name="external" /></a>
              <a href={`${REPOSITORY}/issues`} target="_blank" rel="noreferrer">Feedback & issues <Icon name="external" /></a>
            </div>
          </footer>
        </main>
      </div>
    </div>
  );
}
