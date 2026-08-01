"""Contract tests for bounded GitHub repository retrieval."""

import io
import tarfile

import httpx2
import pytest

from repolume_worker.errors import RepositoryRetrievalError
from repolume_worker.limits import RetrievalLimits
from repolume_worker.retrieval import GitHubRepositoryRetriever, RepositoryRequest

COMMIT_SHA = "a" * 40
ARCHIVE_LOCATION = f"https://codeload.github.com/octocat/Hello-World/legacy.tar.gz/{COMMIT_SHA}"


def _archive_bytes() -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        root = tarfile.TarInfo("octocat-Hello-World-sha/")
        root.type = tarfile.DIRTYPE
        archive.addfile(root)

        content = b"# Hello World\n"
        readme = tarfile.TarInfo("octocat-Hello-World-sha/README.md")
        readme.size = len(content)
        archive.addfile(readme, io.BytesIO(content))
    return output.getvalue()


def _successful_handler(requests: list[httpx2.Request]):
    archive = _archive_bytes()

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        if request.url.path == "/repos/octocat/Hello-World":
            return httpx2.Response(200, json={"private": False, "default_branch": "main"})
        if request.url.path == "/repos/octocat/Hello-World/commits/feature/parser":
            return httpx2.Response(200, json={"sha": COMMIT_SHA})
        if request.url.path == f"/repos/octocat/Hello-World/tarball/{COMMIT_SHA}":
            return httpx2.Response(302, headers={"location": ARCHIVE_LOCATION})
        if str(request.url) == ARCHIVE_LOCATION:
            return httpx2.Response(200, stream=httpx2.ByteStream(archive))
        raise AssertionError(f"Unexpected request: {request.url}")

    return handler


def test_retrieves_immutable_snapshot_and_cleans_it_up() -> None:
    requests: list[httpx2.Request] = []
    client = httpx2.Client(
        transport=httpx2.MockTransport(_successful_handler(requests)),
        follow_redirects=False,
    )
    retriever = GitHubRepositoryRetriever(client=client)
    request = RepositoryRequest("octocat", "Hello-World", "feature/parser")

    with retriever.retrieve(request) as repository:
        source_path = repository.source_path
        assert source_path.exists()
        assert (source_path / "README.md").read_bytes() == b"# Hello World\n"
        assert repository.commit_sha == COMMIT_SHA
        assert repository.file_count == 1
        assert repository.expanded_bytes == 14

    assert not source_path.exists()
    assert len(requests) == 4
    assert b"feature%2Fparser" in requests[1].url.raw_path


def test_uses_default_branch_when_ref_is_omitted() -> None:
    archive = _archive_bytes()

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/repos/octocat/Hello-World":
            return httpx2.Response(200, json={"private": False, "default_branch": "main"})
        if request.url.path == "/repos/octocat/Hello-World/commits/main":
            return httpx2.Response(200, json={"sha": COMMIT_SHA})
        if request.url.path == f"/repos/octocat/Hello-World/tarball/{COMMIT_SHA}":
            return httpx2.Response(302, headers={"location": ARCHIVE_LOCATION})
        return httpx2.Response(200, stream=httpx2.ByteStream(archive))

    client = httpx2.Client(transport=httpx2.MockTransport(handler), follow_redirects=False)
    retriever = GitHubRepositoryRetriever(client=client)

    with retriever.retrieve(RepositoryRequest("octocat", "Hello-World")) as repository:
        assert repository.requested_ref is None
        assert repository.commit_sha == COMMIT_SHA


def test_rejects_repository_that_is_not_public() -> None:
    def handler(_request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"private": True, "default_branch": "main"})

    client = httpx2.Client(transport=httpx2.MockTransport(handler))
    retriever = GitHubRepositoryRetriever(client=client)

    with (
        pytest.raises(RepositoryRetrievalError) as raised,
        retriever.retrieve(RepositoryRequest("octocat", "Hello-World")),
    ):
        pass

    assert raised.value.code == "repository_not_public"


@pytest.mark.parametrize(
    "location",
    [
        f"http://codeload.github.com/octocat/Hello-World/legacy.tar.gz/{COMMIT_SHA}",
        f"https://evil.test/octocat/Hello-World/legacy.tar.gz/{COMMIT_SHA}",
        f"https://codeload.github.com.evil.test/octocat/Hello-World/legacy.tar.gz/{COMMIT_SHA}",
        f"https://user@codeload.github.com/octocat/Hello-World/legacy.tar.gz/{COMMIT_SHA}",
        f"https://codeload.github.com:443/octocat/Hello-World/legacy.tar.gz/{COMMIT_SHA}",
        f"https://codeload.github.com/octocat/Other/legacy.tar.gz/{COMMIT_SHA}",
        f"https://codeload.github.com/octocat/Hello-World/legacy.tar.gz/{COMMIT_SHA}?token=x",
    ],
)
def test_rejects_unsafe_archive_redirects(location: str) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/repos/octocat/Hello-World":
            return httpx2.Response(200, json={"private": False, "default_branch": "main"})
        if request.url.path == "/repos/octocat/Hello-World/commits/main":
            return httpx2.Response(200, json={"sha": COMMIT_SHA})
        return httpx2.Response(302, headers={"location": location})

    client = httpx2.Client(transport=httpx2.MockTransport(handler), follow_redirects=False)
    retriever = GitHubRepositoryRetriever(client=client)

    with (
        pytest.raises(RepositoryRetrievalError) as raised,
        retriever.retrieve(RepositoryRequest("octocat", "Hello-World")),
    ):
        pass

    assert raised.value.code == "archive_redirect_rejected"


def test_rejects_declared_archive_beyond_compressed_limit() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/repos/octocat/Hello-World":
            return httpx2.Response(200, json={"private": False, "default_branch": "main"})
        if request.url.path == "/repos/octocat/Hello-World/commits/main":
            return httpx2.Response(200, json={"sha": COMMIT_SHA})
        if request.url.path == f"/repos/octocat/Hello-World/tarball/{COMMIT_SHA}":
            return httpx2.Response(302, headers={"location": ARCHIVE_LOCATION})
        return httpx2.Response(200, headers={"content-length": "11"}, content=b"too large!!")

    client = httpx2.Client(transport=httpx2.MockTransport(handler), follow_redirects=False)
    limits = RetrievalLimits(max_archive_bytes=10)
    retriever = GitHubRepositoryRetriever(client=client, limits=limits)

    with (
        pytest.raises(RepositoryRetrievalError) as raised,
        retriever.retrieve(RepositoryRequest("octocat", "Hello-World")),
    ):
        pass

    assert raised.value.code == "archive_limit_exceeded"


def test_maps_github_rate_limit_to_safe_error() -> None:
    client = httpx2.Client(
        transport=httpx2.MockTransport(lambda _request: httpx2.Response(403, text="details"))
    )
    retriever = GitHubRepositoryRetriever(client=client)

    with (
        pytest.raises(RepositoryRetrievalError) as raised,
        retriever.retrieve(RepositoryRequest("octocat", "Hello-World")),
    ):
        pass

    assert raised.value.code == "github_rate_limited"
    assert "details" not in raised.value.message


@pytest.mark.parametrize(
    ("owner", "repository", "ref"),
    [
        ("-owner", "repository", None),
        ("owner", "repository name", None),
        ("owner", "..", None),
        ("owner", "repository", "feature ref"),
        ("owner", "repository", "/main"),
        ("owner", "repository", "feature..parser"),
        ("owner", "repository", "feature/.hidden"),
    ],
)
def test_request_requires_normalized_coordinates(
    owner: str,
    repository: str,
    ref: str | None,
) -> None:
    with pytest.raises(ValueError, match="normalized"):
        RepositoryRequest(owner, repository, ref)


def test_rejects_streamed_archive_beyond_compressed_limit() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/repos/octocat/Hello-World":
            return httpx2.Response(200, json={"private": False, "default_branch": "main"})
        if request.url.path == "/repos/octocat/Hello-World/commits/main":
            return httpx2.Response(200, json={"sha": COMMIT_SHA})
        if request.url.path == f"/repos/octocat/Hello-World/tarball/{COMMIT_SHA}":
            return httpx2.Response(302, headers={"location": ARCHIVE_LOCATION})
        return httpx2.Response(200, stream=httpx2.ByteStream(b"12345678901"))

    client = httpx2.Client(transport=httpx2.MockTransport(handler), follow_redirects=False)
    retriever = GitHubRepositoryRetriever(
        client=client, limits=RetrievalLimits(max_archive_bytes=10)
    )

    with (
        pytest.raises(RepositoryRetrievalError) as raised,
        retriever.retrieve(RepositoryRequest("octocat", "Hello-World")),
    ):
        pass

    assert raised.value.code == "archive_limit_exceeded"


def test_requires_manual_redirect_handling() -> None:
    client = httpx2.Client(
        transport=httpx2.MockTransport(lambda _request: httpx2.Response(200)),
        follow_redirects=True,
    )

    with pytest.raises(ValueError, match="redirect"):
        GitHubRepositoryRetriever(client=client)
