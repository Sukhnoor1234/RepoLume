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
  const component = await readFile(
    new URL("../app/components/repository-analyzer.tsx", import.meta.url),
    "utf8",
  );
  const submitRoute = await readFile(
    new URL("../app/api/analyses/route.ts", import.meta.url),
    "utf8",
  );

  assert.match(page, /<RepositoryAnalyzer \/>/);
  assert.match(component, /onSubmit=\{submit\}/);
  assert.match(component, /fetch\("\/api\/analyses"/);
  assert.match(component, /aria-live="polite"/);
  assert.doesNotMatch(component, /REPOLUME_API_URL|dangerouslySetInnerHTML/);
  assert.match(submitRoute, /proxyApiRequest\("\/v1\/analyses"/);
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

test("proxies submission and status through the configured API origin", async () => {
  const received = [];
  const server = createServer(async (incoming, outgoing) => {
    let body = "";
    for await (const chunk of incoming) body += chunk;
    received.push({ method: incoming.method, url: incoming.url, body });
    outgoing.setHeader("content-type", "application/json");
    if (incoming.method === "POST") {
      outgoing.writeHead(202);
      outgoing.end(JSON.stringify({ analysis_id: "analysis_web", status: "queued" }));
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

    assert.equal(submission.status, 202);
    assert.deepEqual(await submission.json(), { analysis_id: "analysis_web", status: "queued" });
    assert.equal(status.status, 200);
    assert.equal((await status.json()).result_available, true);
    assert.deepEqual(
      received.map(({ method, url }) => ({ method, url })),
      [
        { method: "POST", url: "/v1/analyses" },
        { method: "GET", url: "/v1/analyses/analysis_web" },
      ],
    );
  } finally {
    delete process.env.REPOLUME_API_URL;
    await new Promise((resolve, reject) =>
      server.close((error) => (error ? reject(error) : resolve())),
    );
  }
});
