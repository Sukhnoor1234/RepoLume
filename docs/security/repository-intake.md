# Repository intake security boundary

RepoLume treats every repository reference and every future repository archive
as untrusted input. The current checkpoint implements local preflight validation
only. It does not contact GitHub, confirm that a repository exists or is public,
download an archive, clone Git history, or execute repository code.

## Current controls

The API accepts only:

- HTTPS URLs whose host is exactly `github.com`
- paths containing one GitHub owner and one repository name
- an optional conservative branch, tag, or commit reference

It rejects credentials, ports, subdomains, IP addresses, queries, fragments,
encoded paths, extra path segments, malformed names, and unsafe Git ref
patterns. A `.git` suffix and one trailing slash are removed when the canonical
URL is created.

Validation is intentionally stricter than every value Git may technically
accept. Supporting an unusual name later should be an explicit design decision,
not an accidental expansion of the network boundary.

## Requirements for the download checkpoint

Future retrieval must:

1. Build requests from the normalized owner, repository, and ref rather than
   requesting the submitted URL.
2. Resolve a branch or tag to a commit ID and store that immutable ID with the
   analysis.
3. Disable automatic redirects. Validate every redirect target against a small,
   documented GitHub archive-host allowlist before following it.
4. Use outbound network allowlists, short connection and response timeouts, and
   bounded response streaming.
5. Reject archives that exceed the compressed-size, expanded-size, file-count,
   or path-depth limits.
6. Extract into an isolated temporary directory while rejecting absolute paths,
   parent traversal, links, devices, and other special files.
7. Analyze files as data. Never run repository scripts, hooks, builds, package
   managers, or imported code.
8. Delete temporary source data after the retention window, including failed
   and cancelled analyses.

Initial limits will be selected and tested during the retrieval checkpoint.
Until those controls exist, repository download endpoints must remain disabled.

## Ref validation

The ref validator follows Git's unsafe-name restrictions and adds a conservative
character allowlist. Ref values are data, not command text. Any future Git
process must still use argument arrays, an end-of-options marker where
supported, and no shell interpolation.

## References

- [Git ref naming rules](https://git-scm.com/docs/git-check-ref-format)
- [GitHub REST repository contents and archives](https://docs.github.com/en/rest/repos/contents)
- [GitHub source code archive guidance](https://docs.github.com/en/repositories/working-with-files/using-files/downloading-source-code-archives)
