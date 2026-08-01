"""Bounded retrieval of immutable public GitHub repository snapshots."""

import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote, urlsplit

import httpx2

from repolume_worker import __version__
from repolume_worker.archives import extract_repository_archive
from repolume_worker.errors import RepositoryRetrievalError
from repolume_worker.limits import RetrievalLimits

_API_BASE_URL = "https://api.github.com"
_ARCHIVE_HOST = "codeload.github.com"
_API_VERSION = "2026-03-10"
_MAX_METADATA_BYTES = 1024 * 1024
_OWNER_PATTERN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", re.ASCII)
_REPOSITORY_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,100}", re.ASCII)
_REF_PATTERN = re.compile(r"[A-Za-z0-9._/-]{1,255}", re.ASCII)
_SHA_PATTERN = re.compile(r"[0-9a-fA-F]{40}", re.ASCII)


def _is_normalized_ref(ref: str | None) -> bool:
    if ref is None:
        return True
    components = ref.split("/")
    return (
        bool(_REF_PATTERN.fullmatch(ref))
        and not ref.startswith(("-", "/"))
        and not ref.endswith(("/", "."))
        and ".." not in ref
        and "//" not in ref
        and all(
            not component.startswith(".") and not component.endswith(".lock")
            for component in components
        )
    )


@dataclass(frozen=True, slots=True)
class RepositoryRequest:
    """Normalized repository coordinates accepted from the API boundary."""

    owner: str
    repository: str
    ref: str | None = None

    def __post_init__(self) -> None:
        owner_is_valid = bool(_OWNER_PATTERN.fullmatch(self.owner)) and "--" not in self.owner
        repository_is_valid = bool(
            _REPOSITORY_PATTERN.fullmatch(self.repository)
        ) and self.repository not in {".", ".."}
        ref_is_valid = _is_normalized_ref(self.ref)
        if not owner_is_valid or not repository_is_valid or not ref_is_valid:
            raise ValueError("RepositoryRequest requires normalized GitHub coordinates")


@dataclass(frozen=True, slots=True)
class RetrievedRepository:
    """An isolated repository snapshot available only inside retrieval context."""

    owner: str
    repository: str
    requested_ref: str | None
    commit_sha: str
    source_path: Path
    file_count: int
    expanded_bytes: int


class GitHubRepositoryRetriever:
    """Retrieve public GitHub snapshots through explicitly allowed hosts."""

    def __init__(
        self,
        *,
        limits: RetrievalLimits | None = None,
        client: httpx2.Client | None = None,
    ) -> None:
        self.limits = limits or RetrievalLimits()
        if client is not None and client.follow_redirects:
            raise ValueError("Repository retrieval requires redirect following to be disabled")
        self._owns_client = client is None
        self._client = client or httpx2.Client(
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": f"RepoLume-Worker/{__version__}",
                "X-GitHub-Api-Version": _API_VERSION,
            },
            timeout=httpx2.Timeout(30.0, connect=5.0, pool=5.0),
            limits=httpx2.Limits(max_connections=4, max_keepalive_connections=2),
            follow_redirects=False,
            trust_env=False,
        )

    def close(self) -> None:
        """Close an internally owned HTTP client."""

        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "GitHubRepositoryRetriever":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _api_get(self, path: str) -> httpx2.Response:
        try:
            return self._client.get(f"{_API_BASE_URL}{path}")
        except httpx2.HTTPError as exc:
            raise RepositoryRetrievalError(
                "github_unavailable",
                "GitHub could not be reached while retrieving the repository.",
            ) from exc

    @staticmethod
    def _raise_api_failure(response: httpx2.Response, not_found_code: str) -> None:
        if response.status_code == 404:
            raise RepositoryRetrievalError(
                not_found_code, "The GitHub repository or ref was not found."
            )
        if response.status_code in {403, 429}:
            raise RepositoryRetrievalError(
                "github_rate_limited",
                "GitHub temporarily refused the repository request.",
            )
        raise RepositoryRetrievalError(
            "github_unavailable",
            "GitHub returned an unexpected response while retrieving the repository.",
        )

    @staticmethod
    def _json_object(response: httpx2.Response) -> dict[str, object]:
        if len(response.content) > _MAX_METADATA_BYTES:
            raise RepositoryRetrievalError(
                "github_invalid_response",
                "GitHub returned repository metadata beyond the supported limit.",
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise RepositoryRetrievalError(
                "github_invalid_response",
                "GitHub returned invalid repository metadata.",
            ) from exc
        if not isinstance(payload, dict):
            raise RepositoryRetrievalError(
                "github_invalid_response",
                "GitHub returned invalid repository metadata.",
            )
        return payload

    def _resolve_commit(self, request: RepositoryRequest) -> str:
        repository_path = f"/repos/{request.owner}/{request.repository}"
        repository_response = self._api_get(repository_path)
        if repository_response.status_code != 200:
            self._raise_api_failure(repository_response, "repository_not_found")
        repository_data = self._json_object(repository_response)
        if repository_data.get("private") is not False:
            raise RepositoryRetrievalError(
                "repository_not_public",
                "Only public GitHub repositories can be retrieved.",
            )

        selected_ref = request.ref or repository_data.get("default_branch")
        if not isinstance(selected_ref, str) or not _REF_PATTERN.fullmatch(selected_ref):
            raise RepositoryRetrievalError(
                "github_invalid_response",
                "GitHub returned an invalid default branch.",
            )

        encoded_ref = quote(selected_ref, safe="")
        commit_response = self._api_get(f"{repository_path}/commits/{encoded_ref}")
        if commit_response.status_code != 200:
            self._raise_api_failure(commit_response, "repository_ref_not_found")
        commit_data = self._json_object(commit_response)
        commit_sha = commit_data.get("sha")
        if not isinstance(commit_sha, str) or not _SHA_PATTERN.fullmatch(commit_sha):
            raise RepositoryRetrievalError(
                "github_invalid_response",
                "GitHub returned an invalid commit identifier.",
            )
        return commit_sha.lower()

    def _archive_location(self, request: RepositoryRequest, commit_sha: str) -> str:
        response = self._api_get(
            f"/repos/{request.owner}/{request.repository}/tarball/{commit_sha}"
        )
        if response.status_code != 302:
            self._raise_api_failure(response, "repository_archive_not_found")
        location = response.headers.get("location")
        if location is None:
            raise RepositoryRetrievalError(
                "github_invalid_response",
                "GitHub did not provide a repository archive location.",
            )

        try:
            parsed = urlsplit(location)
            port = parsed.port
        except ValueError as exc:
            raise RepositoryRetrievalError(
                "archive_redirect_rejected",
                "GitHub returned an unsafe repository archive location.",
            ) from exc

        path_parts = parsed.path.split("/")
        path_is_expected = (
            len(path_parts) == 5
            and not path_parts[0]
            and path_parts[1].casefold() == request.owner.casefold()
            and path_parts[2].casefold() == request.repository.casefold()
            and path_parts[3] == "legacy.tar.gz"
            and path_parts[4].casefold() == commit_sha.casefold()
        )
        if (
            parsed.scheme != "https"
            or parsed.hostname != _ARCHIVE_HOST
            or port is not None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or "%" in parsed.path
            or not path_is_expected
        ):
            raise RepositoryRetrievalError(
                "archive_redirect_rejected",
                "GitHub returned an unsafe repository archive location.",
            )
        return location

    def _download_archive(self, location: str, archive_path: Path) -> None:
        try:
            with self._client.stream("GET", location) as response:
                if response.status_code != 200:
                    self._raise_api_failure(response, "repository_archive_not_found")

                content_length = response.headers.get("content-length")
                if content_length is not None:
                    try:
                        declared_bytes = int(content_length)
                    except ValueError as exc:
                        raise RepositoryRetrievalError(
                            "github_invalid_response",
                            "GitHub returned an invalid archive size.",
                        ) from exc
                    if declared_bytes < 0 or declared_bytes > self.limits.max_archive_bytes:
                        raise RepositoryRetrievalError(
                            "archive_limit_exceeded",
                            "The compressed repository is beyond the supported size limit.",
                        )

                downloaded_bytes = 0
                with archive_path.open("xb") as output:
                    for chunk in response.iter_raw():
                        downloaded_bytes += len(chunk)
                        if downloaded_bytes > self.limits.max_archive_bytes:
                            raise RepositoryRetrievalError(
                                "archive_limit_exceeded",
                                "The compressed repository is beyond the supported size limit.",
                            )
                        output.write(chunk)
        except RepositoryRetrievalError:
            raise
        except (OSError, httpx2.HTTPError) as exc:
            raise RepositoryRetrievalError(
                "repository_download_failed",
                "The repository archive could not be downloaded.",
            ) from exc

    @contextmanager
    def retrieve(self, request: RepositoryRequest) -> Iterator[RetrievedRepository]:
        """Yield an isolated snapshot and always remove it when the context exits."""

        temporary_directory = TemporaryDirectory(prefix="repolume-repository-")
        try:
            temporary_path = Path(temporary_directory.name)
            archive_path = temporary_path / "repository.tar.gz"
            source_path = temporary_path / "source"

            commit_sha = self._resolve_commit(request)
            location = self._archive_location(request, commit_sha)
            self._download_archive(location, archive_path)
            extraction = extract_repository_archive(archive_path, source_path, self.limits)
            try:
                archive_path.unlink()
            except OSError as exc:
                raise RepositoryRetrievalError(
                    "repository_cleanup_failed",
                    "Temporary repository files could not be removed.",
                ) from exc

            yield RetrievedRepository(
                owner=request.owner,
                repository=request.repository,
                requested_ref=request.ref,
                commit_sha=commit_sha,
                source_path=source_path,
                file_count=extraction.file_count,
                expanded_bytes=extraction.expanded_bytes,
            )
        finally:
            try:
                temporary_directory.cleanup()
            except OSError as exc:
                raise RepositoryRetrievalError(
                    "repository_cleanup_failed",
                    "Temporary repository files could not be removed.",
                ) from exc
