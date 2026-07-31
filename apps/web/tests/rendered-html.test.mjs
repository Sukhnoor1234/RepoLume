import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request("http://localhost/", { headers: { accept: "text/html" } }),
    { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } },
    { waitUntil() {}, passThroughOnException() {} },
  );
}

test("server-renders the RepoLume foundation page", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<title>RepoLume — AI Architecture Explorer<\/title>/i);
  assert.match(html, /Understand any codebase before you touch it\./);
  assert.match(html, /AI architecture explorer/i);
  assert.match(html, /commerce-platform/);
  assert.match(html, /Repository analysis will be added in a later milestone\./);
  assert.doesNotMatch(html, /Starter Project|loading skeleton/i);
});

test("keeps unfinished functionality disabled", async () => {
  const page = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");
  assert.match(page, /button type="button" disabled/);
  assert.match(page, /readOnly/);
  assert.doesNotMatch(page, /fetch\(|onSubmit|action=/);
});