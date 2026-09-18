# Security policy

RepoLume is an actively developed portfolio project. The public deployment is
currently a sample-first demo: live repository ingestion and the private
analysis backend are not exposed to internet visitors.

## Reporting a vulnerability

Please do not publish exploitable details in a public issue. Use the
repository's **Security** tab to submit a private vulnerability report. Include
the affected route or component, reproduction steps, and the impact you
observed.

If private reporting is temporarily unavailable, open a public issue that only
states that you need a private security contact. Do not include the exploit,
credentials, repository contents, or personal information.

## Supported version

Only the current `main` branch and the deployment linked from the repository
homepage are supported. Security fixes are applied to the latest version rather
than backported to older checkpoints.

## Public demo boundary

- Built-in sample repositories contain no user data.
- Live repository submission is disabled unless a private API URL is explicitly
  configured by the deployer.
- Deployment credentials are stored outside the repository.
- The web worker returns restrictive browser security headers.
