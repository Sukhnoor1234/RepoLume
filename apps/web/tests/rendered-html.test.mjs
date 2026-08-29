import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createServer } from "node:http";
import test from "node:test";

let workerImportSequence = 0;

async function request(path = "/", init) {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${workerImportSequence++}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request(`http://localhost${path}`, init),
    { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } },
    { waitUntil() {}, passThroughOnException() {} },
  );
}

test("server-renders the RepoLume analysis entry point", async () => {
  const response = await request("/", { headers: { accept: "text/html" } });
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<title>RepoLume — AI Architecture Explorer<\/title>/i);
  assert.match(html, /Understand any codebase before you touch it\./);
  assert.match(html, /AI architecture explorer/i);
  assert.match(html, /commerce-platform/);
  assert.match(html, /Public GitHub repositories only/);
  assert.match(html, /Analyze repository/);
  assert.doesNotMatch(html, /Starter Project|loading skeleton/i);
});

test("connects the repository form through same-origin analysis routes", async () => {
  const page = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");
  const experience = await readFile(
    new URL("../app/components/analysis-experience.tsx", import.meta.url),
    "utf8",
  );
  const component = await readFile(
    new URL("../app/components/repository-analyzer.tsx", import.meta.url),
    "utf8",
  );
  const panel = await readFile(
    new URL("../app/components/architecture-panel.tsx", import.meta.url),
    "utf8",
  );
  const explorer = await readFile(
    new URL("../app/components/architecture-explorer.tsx", import.meta.url),
    "utf8",
  );
  const questionPanel = await readFile(
    new URL("../app/components/repository-question-panel.tsx", import.meta.url),
    "utf8",
  );
  const submitRoute = await readFile(
    new URL("../app/api/analyses/route.ts", import.meta.url),
    "utf8",
  );
  const architectureRoute = await readFile(
    new URL("../app/api/analyses/[analysisId]/architecture/route.ts", import.meta.url),
    "utf8",
  );
  const evidenceRoute = await readFile(
    new URL("../app/api/analyses/[analysisId]/evidence-query/route.ts", import.meta.url),
    "utf8",
  );
  const answerRoute = await readFile(
    new URL("../app/api/analyses/[analysisId]/answer/route.ts", import.meta.url),
    "utf8",
  );

  assert.match(page, /<AnalysisExperience \/>/);
  assert.match(experience, /<RepositoryAnalyzer onArchitectureChange=/);
  assert.match(experience, /<ArchitecturePanel display=/);
  assert.match(experience, /<RepositoryQuestionPanel analysisId=/);
  assert.match(component, /onSubmit=\{submit\}/);
  assert.match(component, /fetch\("\/api\/analyses"/);
  assert.match(component, /\/architecture`/);
  assert.match(component, /aria-live="polite"/);
  assert.doesNotMatch(component, /REPOLUME_API_URL|dangerouslySetInnerHTML/);
  assert.match(panel, /dynamic\(/);
  assert.match(explorer, /<ReactFlow/);
  assert.match(explorer, /source evidence/i);
  assert.match(questionPanel, /Ask RepoLume/);
  assert.match(questionPanel, /parseRepositoryAnswer/);
  assert.match(questionPanel, /Sources used/);
  assert.doesNotMatch(questionPanel, /dangerouslySetInnerHTML|REPOLUME_API_URL/);
  assert.match(submitRoute, /proxyApiRequest\("\/v1\/analyses"/);
  assert.match(
    architectureRoute,
    /`\/v1\/analyses\/\$\{encodeURIComponent\(analysisId\)\}\/architecture`/,
  );
  assert.match(evidenceRoute, /evidence-query`/);
  assert.match(answerRoute, /answer`/);
});

test("rejects malformed repository submissions at the web boundary", async () => {
  const response = await request("/api/analyses", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ unexpected: true }),
  });

  assert.equal(response.status, 400);
  assert.deepEqual(await response.json(), {
    error: {
      code: "validation_error",
      message: "Enter a valid public GitHub repository URL.",
    },
  });
});

test("rejects malformed evidence queries at the web boundary", async () => {
  const response = await request("/api/analyses/analysis_web/evidence-query", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ question: "  " }),
  });

  assert.equal(response.status, 400);
  assert.equal((await response.json()).error.code, "validation_error");
});

test("rejects malformed repository questions at the answer boundary", async () => {
  const response = await request("/api/analyses/analysis_web/answer", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ question: "Where is the app?", extra: true }),
  });

  assert.equal(response.status, 400);
  assert.equal((await response.json()).error.code, "validation_error");
});

test("fails closed when the analysis API is not configured", async () => {
  const response = await request("/api/analyses", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ repository_url: "https://github.com/octocat/Hello-World" }),
  });

  assert.equal(response.status, 503);
  assert.deepEqual(await response.json(), {
    error: {
      code: "analysis_service_unavailable",
      message: "Repository analysis is temporarily unavailable.",
    },
  });
});

test("proxies submission, status, and architecture through the configured API origin", async () => {
  const received = [];
  const server = createServer(async (incoming, outgoing) => {
    let body = "";
    for await (const chunk of incoming) body += chunk;
    received.push({ method: incoming.method, url: incoming.url, body });
    outgoing.setHeader("content-type", "application/json");
    if (incoming.method === "POST" && incoming.url?.endsWith("/answer")) {
      outgoing.writeHead(200);
      outgoing.end(
        JSON.stringify({
          schema_version: "1.0",
          question: "Where is the app module?",
          answer: "The strongest source evidence points to app.py [1].",
          grounding_status: "supported",
          citations: [
            {
              node_id: "module:python:app.py",
              kind: "module",
              name: "app",
              language: "python",
              location: { path: "app.py", line: 1, end_line: 10 },
              confidence: "confirmed",
              score: 7,
              matched_terms: ["app", "module"],
              relationship_count: 1,
            },
          ],
        }),
      );
      return;
    }
    if (incoming.method === "POST" && incoming.url?.endsWith("/evidence-query")) {
      outgoing.writeHead(200);
      outgoing.end(
        JSON.stringify({
          schema_version: "1.0",
          question: "Where is the app module?",
          matches: [
            {
              node_id: "module:python:app.py",
              kind: "module",
              name: "app",
              language: "python",
              location: { path: "app.py", line: 1, end_line: 10 },
              confidence: "confirmed",
              score: 7,
              matched_terms: ["app", "module"],
              relationship_count: 1,
            },
          ],
        }),
      );
      return;
    }
    if (incoming.method === "POST") {
      outgoing.writeHead(202);
      outgoing.end(JSON.stringify({ analysis_id: "analysis_web", status: "queued" }));
      return;
    }
    if (incoming.url?.endsWith("/architecture")) {
      outgoing.writeHead(200);
      outgoing.end(
        JSON.stringify({
          schema_version: "1.0",
          languages: ["python"],
          nodes: [
            {
              id: "repository",
              kind: "repository",
              name: "Repository",
              language: null,
              location: null,
              qualified_name: null,
              symbol_kind: null,
              detail: null,
              confidence: "confirmed",
              decorators: [],
              source_bytes: null,
              line_count: null,
            },
            {
              id: "module:python:app.py",
              kind: "module",
              name: "app",
              language: "python",
              location: { path: "app.py", line: 1, end_line: 10 },
              qualified_name: "app",
              symbol_kind: null,
              detail: null,
              confidence: "confirmed",
              decorators: [],
              source_bytes: 100,
              line_count: 10,
            },
          ],
          edges: [
            {
              id: "edge:contains",
              kind: "contains",
              source: "repository",
              target: "module:python:app.py",
              confidence: "confirmed",
              location: { path: "app.py", line: 1, end_line: 1 },
            },
          ],
          diagnostics: [],
          summary: {
            language_count: 1,
            node_count: 2,
            edge_count: 1,
            module_count: 1,
            symbol_count: 0,
            entry_point_count: 0,
            external_dependency_count: 0,
            dependency_count: 0,
            diagnostic_count: 0,
          },
        }),
      );
      return;
    }
    outgoing.writeHead(200);
    outgoing.end(
      JSON.stringify({
        analysis_id: "analysis_web",
        status: "completed",
        repository: {
          provider: "github",
          owner: "octocat",
          repository: "Hello-World",
          canonical_url: "https://github.com/octocat/Hello-World",
          ref: null,
        },
        result_available: true,
        failure: null,
      }),
    );
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  assert.notEqual(typeof address, "string");
  process.env.REPOLUME_API_URL = `http://127.0.0.1:${address.port}`;

  try {
    const submission = await request("/api/analyses", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ repository_url: "https://github.com/octocat/Hello-World" }),
    });
    const status = await request("/api/analyses/analysis_web");
    const architecture = await request("/api/analyses/analysis_web/architecture");
    const evidence = await request("/api/analyses/analysis_web/evidence-query", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ question: "Where is the app module?", limit: 5 }),
    });
    const answer = await request("/api/analyses/analysis_web/answer", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ question: "Where is the app module?", limit: 5 }),
    });

    assert.equal(submission.status, 202);
    assert.deepEqual(await submission.json(), { analysis_id: "analysis_web", status: "queued" });
    assert.equal(status.status, 200);
    assert.equal((await status.json()).result_available, true);
    assert.equal(architecture.status, 200);
    assert.equal((await architecture.json()).schema_version, "1.0");
    assert.equal(evidence.status, 200);
    assert.equal((await evidence.json()).matches[0].location.path, "app.py");
    assert.equal(answer.status, 200);
    assert.equal((await answer.json()).grounding_status, "supported");
    assert.deepEqual(
      received.map(({ method, url }) => ({ method, url })),
      [
        { method: "POST", url: "/v1/analyses" },
        { method: "GET", url: "/v1/analyses/analysis_web" },
        { method: "GET", url: "/v1/analyses/analysis_web/architecture" },
        { method: "POST", url: "/v1/analyses/analysis_web/evidence-query" },
        { method: "POST", url: "/v1/analyses/analysis_web/answer" },
      ],
    );
  } finally {
    delete process.env.REPOLUME_API_URL;
    await new Promise((resolve, reject) =>
      server.close((error) => (error ? reject(error) : resolve())),
    );
  }
});
