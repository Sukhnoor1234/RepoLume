# Contributing to RepoLume

RepoLume is being developed in small, reviewable milestones. Changes should
keep the repository runnable and should not introduce work from a later
milestone early.

## Branch workflow

1. Start from the latest `main`.
2. Create a focused branch using a short purpose-oriented prefix such as
   `feature/`, `fix/`, `docs/`, or `chore/`.
3. Keep each branch limited to one coherent change.
4. Open a pull request and wait for required checks to pass.
5. Review the complete diff before merging.
6. Prefer squash merging so `main` keeps a concise milestone history.

Direct feature commits to `main` are not part of the normal workflow.

## Commit expectations

- Use an imperative summary that explains the outcome.
- Keep unrelated changes in separate commits.
- Never commit credentials, access tokens, private keys, local environment
  files, or repository source submitted for analysis.
- Document architectural decisions that meaningfully change system boundaries,
  data flow, security, or deployment.

## Quality checks

Every pull request should eventually include checks appropriate to the code it
changes:

- Formatting and linting
- Type checking
- Automated tests
- Production build validation
- Security-sensitive tests when repository ingestion or source handling changes

The exact commands will be added when the applications are scaffolded.

## Pull request description

Each pull request should state:

- What changed and why
- What is intentionally out of scope
- How the change was verified
- Screenshots or recordings for visible interface changes
- Follow-up work, limitations, or risks

## Reporting security issues

Do not open a public issue containing a vulnerability, secret, or private
repository content. A private reporting process will be documented before the
public launch.
