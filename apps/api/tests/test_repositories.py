"""Tests for repository reference validation."""

import pytest

from repolume_api.repositories import RepositoryReferenceError, normalize_repository_reference


@pytest.mark.parametrize(
    ("repository_url", "expected_url"),
    [
        (
            "https://github.com/octocat/Hello-World",
            "https://github.com/octocat/Hello-World",
        ),
        (
            "HTTPS://GITHUB.COM/octocat/Hello-World.git/",
            "https://github.com/octocat/Hello-World",
        ),
    ],
)
def test_normalizes_supported_github_urls(repository_url: str, expected_url: str) -> None:
    reference = normalize_repository_reference(repository_url, "feature/parser")

    assert reference.canonical_url == expected_url
    assert reference.ref == "feature/parser"


@pytest.mark.parametrize(
    ("repository_url", "expected_code"),
    [
        ("http://github.com/owner/repository", "repository_url_invalid"),
        ("git://github.com/owner/repository", "repository_url_invalid"),
        ("file:///owner/repository", "repository_url_invalid"),
        ("https://example.com/owner/repository", "repository_host_not_supported"),
        ("https://github.com.evil.test/owner/repository", "repository_host_not_supported"),
        ("https://127.0.0.1/owner/repository", "repository_host_not_supported"),
        ("https://localhost/owner/repository", "repository_host_not_supported"),
        ("https://github.com@evil.test/owner/repository", "repository_url_invalid"),
        ("https://user:secret@github.com/owner/repository", "repository_url_invalid"),
        ("https://github.com:443/owner/repository", "repository_url_invalid"),
        ("https://github.com/owner", "repository_path_invalid"),
        ("https://github.com/owner/repository/issues", "repository_path_invalid"),
        ("https://github.com/owner/repository?tab=readme", "repository_url_invalid"),
        ("https://github.com/owner/repository?", "repository_url_invalid"),
        ("https://github.com/owner/repository#readme", "repository_url_invalid"),
        ("https://github.com/owner/repository#", "repository_url_invalid"),
        ("https://github.com/owner%2Frepository", "repository_url_invalid"),
        ("https://github.com/owner/repository%2Fissues", "repository_url_invalid"),
        ("https://github.com/owner\\repository", "repository_url_invalid"),
        (" https://github.com/owner/repository", "repository_url_invalid"),
        ("https://github.com/-owner/repository", "repository_path_invalid"),
        ("https://github.com/owner-/repository", "repository_path_invalid"),
        ("https://github.com/owner/repository name", "repository_path_invalid"),
        ("https://github.com/owner/..", "repository_path_invalid"),
    ],
)
def test_rejects_unsafe_repository_urls(repository_url: str, expected_code: str) -> None:
    with pytest.raises(RepositoryReferenceError) as raised:
        normalize_repository_reference(repository_url)

    assert raised.value.code == expected_code


@pytest.mark.parametrize(
    "ref",
    [
        "-branch",
        "/branch",
        "branch/",
        "feature//parser",
        "feature..parser",
        ".hidden",
        "feature/.hidden",
        "release.lock",
        "feature/release.lock",
        "@",
        "feature@{one",
        "feature parser",
        "feature~parser",
        "feature^parser",
        "feature:parser",
        "feature?parser",
        "feature*parser",
        "feature[parser",
        "feature\\parser",
    ],
)
def test_rejects_unsafe_git_refs(ref: str) -> None:
    with pytest.raises(RepositoryReferenceError) as raised:
        normalize_repository_reference("https://github.com/owner/repository", ref)

    assert raised.value.code == "repository_ref_invalid"


def test_accepts_commit_sha_as_ref() -> None:
    sha = "a" * 40

    reference = normalize_repository_reference("https://github.com/owner/repository", sha)

    assert reference.ref == sha
