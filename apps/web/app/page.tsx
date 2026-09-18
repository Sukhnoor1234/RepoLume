import { AnalysisExperience } from "@/app/components/analysis-experience";
import { isLiveAnalysisEnabled } from "@/app/lib/repolume-runtime";

export const dynamic = "force-dynamic";

export default function Home() {
  const liveAnalysisEnabled = isLiveAnalysisEnabled();

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

      <AnalysisExperience liveAnalysisEnabled={liveAnalysisEnabled} />

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
