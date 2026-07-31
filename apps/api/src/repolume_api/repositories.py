"""Pure validation and normalization for repository references."""

import re
from dataclasses import dataclass
from urllib.parse import SplitResult, urlsplit

_OWNER_PATTERN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", re.ASCII)
_REPOSITORY_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,100}", re.ASCII)
_REF_PATTERN = re.compile(r"[A-Za-z0-9._/-]{1,255}", re.ASCII)


class RepositoryReferenceError(ValueError):
    """A safe, user-facing repository reference validation error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class RepositoryReference:
    """A normalized GitHub repository and optional Git ref."""

    owner: str
    repository: str
    ref: str | None

    @property
    def canonical_url(self) -> str:
        return f"https://github.com/{self.owner}/{self.repository}"


def _parse_url(repository_url: str) -> SplitResult:
    if repository_url != repository_url.strip() or "\\" in repository_url:
        raise RepositoryReferenceError(
            "repository_url_invalid",
            "Enter a valid HTTPS GitHub repository URL.",
        )

    try:
        parsed = urlsplit(repository_url)
        _ = parsed.port
    except ValueError as exc:
        raise RepositoryReferenceError(
            "repository_url_invalid",
            "Enter a valid HTTPS GitHub repository URL.",
        ) from exc

    if parsed.scheme.lower() != "https":
        raise RepositoryReferenceError(
            "repository_url_invalid",
            "Repository URLs must use HTTPS.",
        )
    if parsed.username is not None or parsed.password is not None:
        raise RepositoryReferenceError(
            "repository_url_invalid",
            "Credentials are not allowed in repository URLs.",
        )
    if parsed.hostname != "github.com":
        raise RepositoryReferenceError(
            "repository_host_not_supported",
            "Only github.com repositories are supported.",
        )
    if parsed.port is not None:
        raise RepositoryReferenceError(
            "repository_url_invalid",
            "Repository URLs cannot include a port.",
        )
    if "?" in repository_url or "#" in repository_url or "%" in parsed.path:
        raise RepositoryReferenceError(
            "repository_url_invalid",
            "Repository URLs cannot include encoded paths, queries, or fragments.",
        )
    return parsed


def _normalize_path(path: str) -> tuple[str, str]:
    parts = path.removesuffix("/").split("/")
    if len(parts) != 3 or parts[0]:
        raise RepositoryReferenceError(
            "repository_path_invalid",
            "Use a repository URL in the form https://github.com/owner/repository.",
        )

    owner, repository = parts[1], parts[2]
    if repository.lower().endswith(".git"):
        repository = repository[:-4]

    owner_is_valid = bool(_OWNER_PATTERN.fullmatch(owner)) and "--" not in owner
    repository_is_valid = bool(_REPOSITORY_PATTERN.fullmatch(repository))
    if not owner_is_valid or not repository_is_valid or repository in {".", ".."}:
        raise RepositoryReferenceError(
            "repository_path_invalid",
            "The GitHub owner or repository name is invalid.",
        )
    return owner, repository


def _validate_ref(ref: str | None) -> str | None:
    if ref is None:
        return None

    components = ref.split("/")
    is_invalid = (
        ref != ref.strip()
        or not _REF_PATTERN.fullmatch(ref)
        or ref.startswith(("-", "/"))
        or ref.endswith(("/", "."))
        or ".." in ref
        or "//" in ref
        or "@{" in ref
        or ref == "@"
        or any(component.startswith(".") or component.endswith(".lock") for component in components)
    )
    if is_invalid:
        raise RepositoryReferenceError(
            "repository_ref_invalid",
            "Enter a valid branch, tag, or commit reference.",
        )
    return ref


def normalize_repository_reference(
    repository_url: str,
    ref: str | None = None,
) -> RepositoryReference:
    """Validate a GitHub URL and ref without making a network request."""

    parsed = _parse_url(repository_url)
    owner, repository = _normalize_path(parsed.path)
    return RepositoryReference(
        owner=owner,
        repository=repository,
        ref=_validate_ref(ref),
    )
