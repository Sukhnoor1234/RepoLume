# Public demo deployment

RepoLume's first hosted version is a sample-first web demo on Cloudflare
Workers. It shows the real architecture explorer and grounded question flow
without pretending the private analysis backend is online.

Current deployment:
[`repolume-web.sukhnoor-repolume.workers.dev`](https://repolume-web.sukhnoor-repolume.workers.dev)

## Deployment behavior

- Without `REPOLUME_API_URL`, the page displays **Public demo mode**, disables
  new repository submissions, and keeps both built-in samples available.
- With a valid `REPOLUME_API_URL`, the submission form is enabled and the web
  worker proxies analysis requests to FastAPI.
- `/api/health` reports whether live analysis is enabled but never returns the
  configured backend URL.

## First local deployment

From `apps/web`:

```powershell
npx wrangler login
npm run deploy:dry-run
npm run deploy
```

Wrangler prints the generated `workers.dev` URL. Verify it with:

```powershell
npm run smoke -- https://your-repolume-worker.workers.dev
```

Do not commit a Cloudflare account ID, API token, generated `.dev.vars`, or a
private backend URL.

## GitHub deployment

The **Deploy public demo** workflow is manual so merging code cannot publish an
unreviewed production change. Configure these production environment secrets:

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`

Run the workflow from GitHub Actions. Optionally provide the public URL to run
the smoke test immediately after deployment.

## Custom domain

The `workers.dev` deployment is verified and ready to share. A custom domain can
be attached later in Cloudflare; rerun the smoke test against it before
replacing the current URL in the repository and portfolio.

## Rollout boundary

This checkpoint makes the public web demo deployable. It does not expose the
local PostgreSQL, Redis, FastAPI, or worker services to the internet. Hosting
those services is a separate security and operations decision.
