# Repository intake security boundary

RepoLume treats every repository reference and repository archive as untrusted
input. The API performs local preflight validation, and the worker can retrieve
a bounded public GitHub snapshot through a separate security boundary. These
capabilities are not connected to an analysis submission endpoint or queue, and
repository code is never executed.

## API preflight controls

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

## Worker retrieval controls

The worker retrieval implementation:

- constructs requests from normalized coordinates instead of the submitted URL
- verifies that the repository is public and resolves the selected ref to an
  immutable 40-character commit SHA
- disables automatic redirects and accepts only the expected HTTPS archive path
  on `codeload.github.com`
- ignores inherited proxy and credential configuration, uses explicit timeouts,
  and streams archives through compressed-size limits
- inspects every archive entry before extraction and enforces expanded size,
  single-file, entry-count, path-depth, and path-length limits
- rejects traversal, absolute paths, links, special files, collisions, corrupt
  archives, and unsupported cross-platform paths
- removes the compressed archive after extraction and removes the isolated
  source directory whenever processing exits
- never runs repository scripts, hooks, builds, package managers, or imports

The complete limits and failure behavior are documented in
[repository retrieval](../worker/repository-retrieval.md).

## Remaining deployment controls

Before analysis submission is enabled, RepoLume still needs authenticated job
ownership, queue delivery, persistence and retention records, and a
container-level outbound network policy. The source analyzers read the
retrieved directory only while its cleanup context is active. Python uses the
standard-library AST, while TypeScript and JavaScript use Tree-sitter grammars.
Both parse source as data and do not import modules, execute code, install
repository packages, or inspect the host environment. The analysis pipeline
keeps both analyzers and architecture composition inside the retrieval context,
and records completion only after temporary cleanup succeeds.

## Ref validation

The ref validator follows Git's unsafe-name restrictions and adds a conservative
character allowlist. Ref values are data, not command text. Any future Git
process must still use argument arrays, an end-of-options marker where
supported, and no shell interpolation.

## References

- [Git ref naming rules](https://git-scm.com/docs/git-check-ref-format)
- [GitHub REST repository contents and archives](https://docs.github.com/en/rest/repos/contents)
- [GitHub source code archive guidance](https://docs.github.com/en/repositories/working-with-files/using-files/downloading-source-code-archives)
