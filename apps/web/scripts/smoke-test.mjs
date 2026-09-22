import assert from "node:assert/strict";

const deploymentValue = process.argv[2] ?? process.env.REPOLUME_DEPLOYMENT_URL;

if (!deploymentValue) {
  console.error("Usage: npm run smoke -- https://your-repolume-deployment.example");
  process.exitCode = 1;
} else {
  let deploymentUrl;
  try {
    deploymentUrl = new URL(deploymentValue);
    if (!["http:", "https:"].includes(deploymentUrl.protocol)) throw new TypeError();
    deploymentUrl.username = "";
    deploymentUrl.password = "";
    deploymentUrl.search = "";
    deploymentUrl.hash = "";
  } catch {
    console.error("The deployment URL must be a valid HTTP or HTTPS URL.");
    process.exitCode = 1;
  }

  if (deploymentUrl) {
    const request = (path) =>
      fetch(new URL(path, deploymentUrl), {
        headers: { accept: "application/json, text/html;q=0.9" },
        redirect: "follow",
        signal: AbortSignal.timeout(15_000),
      });

    const pageResponse = await request("/");
    assert.equal(pageResponse.status, 200, "The public page should return HTTP 200.");
    const page = await pageResponse.text();
    assert.match(page, /Get to know your codebase/);
    assert.match(page, /Explore a repository/);

    const healthResponse = await request("/api/health");
    assert.equal(healthResponse.status, 200, "The web health endpoint should return HTTP 200.");
    const health = await healthResponse.json();
    assert.equal(health.status, "ok");
    assert.equal(health.service, "repolume-web");

    const sampleResponse = await request("/api/analyses/sample_commerce_platform");
    assert.equal(sampleResponse.status, 200, "The built-in sample should return HTTP 200.");
    const sample = await sampleResponse.json();
    assert.equal(sample.result_available, true);

    console.log(`RepoLume smoke test passed: ${deploymentUrl.origin}`);
  }
}
