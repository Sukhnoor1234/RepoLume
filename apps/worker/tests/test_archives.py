"""Security tests for repository archive extraction."""

import io
import tarfile
from pathlib import Path

import pytest

from repolume_worker.archives import extract_repository_archive
from repolume_worker.errors import RepositoryRetrievalError
from repolume_worker.limits import RetrievalLimits


def _write_archive(
    path: Path,
    files: dict[str, bytes],
    *,
    directories: tuple[str, ...] = ("owner-repository-sha/",),
    symlinks: dict[str, str] | None = None,
) -> None:
    with tarfile.open(path, mode="w:gz") as archive:
        for directory in directories:
            member = tarfile.TarInfo(directory)
            member.type = tarfile.DIRTYPE
            archive.addfile(member)
        for name, content in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
        for name, target in (symlinks or {}).items():
            member = tarfile.TarInfo(name)
            member.type = tarfile.SYMTYPE
            member.linkname = target
            archive.addfile(member)


def test_extracts_regular_files_without_archive_root(tmp_path: Path) -> None:
    archive_path = tmp_path / "repository.tar.gz"
    destination = tmp_path / "source"
    _write_archive(
        archive_path,
        {
            "owner-repository-sha/README.md": b"# Example\n",
            "owner-repository-sha/src/app.py": b"print('hello')\n",
        },
        directories=("owner-repository-sha/", "owner-repository-sha/src/"),
    )

    result = extract_repository_archive(archive_path, destination, RetrievalLimits())

    assert result.file_count == 2
    assert result.expanded_bytes == 25
    assert (destination / "README.md").read_bytes() == b"# Example\n"
    assert (destination / "src" / "app.py").read_bytes() == b"print('hello')\n"
    assert not (destination / "owner-repository-sha").exists()


@pytest.mark.parametrize(
    "unsafe_name",
    [
        "/absolute.txt",
        "owner-repository-sha/../escape.txt",
        "owner-repository-sha/folder\\escape.txt",
        "owner-repository-sha/con.txt",
        "owner-repository-sha/trailing-dot./file.txt",
    ],
)
def test_rejects_unsafe_paths(tmp_path: Path, unsafe_name: str) -> None:
    archive_path = tmp_path / "repository.tar.gz"
    _write_archive(archive_path, {unsafe_name: b"unsafe"})

    with pytest.raises(RepositoryRetrievalError) as raised:
        extract_repository_archive(archive_path, tmp_path / "source", RetrievalLimits())

    assert raised.value.code == "archive_unsafe"


def test_rejects_symbolic_links(tmp_path: Path) -> None:
    archive_path = tmp_path / "repository.tar.gz"
    _write_archive(
        archive_path,
        {"owner-repository-sha/README.md": b"safe"},
        symlinks={"owner-repository-sha/link": "../../outside"},
    )

    with pytest.raises(RepositoryRetrievalError) as raised:
        extract_repository_archive(archive_path, tmp_path / "source", RetrievalLimits())

    assert raised.value.code == "archive_unsafe"


def test_rejects_case_insensitive_path_collisions(tmp_path: Path) -> None:
    archive_path = tmp_path / "repository.tar.gz"
    _write_archive(
        archive_path,
        {
            "owner-repository-sha/README.md": b"one",
            "owner-repository-sha/readme.md": b"two",
        },
    )

    with pytest.raises(RepositoryRetrievalError) as raised:
        extract_repository_archive(archive_path, tmp_path / "source", RetrievalLimits())

    assert raised.value.code == "archive_unsafe"


def test_enforces_expanded_size_limit_before_extraction(tmp_path: Path) -> None:
    archive_path = tmp_path / "repository.tar.gz"
    destination = tmp_path / "source"
    _write_archive(
        archive_path,
        {
            "owner-repository-sha/one.txt": b"123",
            "owner-repository-sha/two.txt": b"456",
        },
    )
    limits = RetrievalLimits(max_expanded_bytes=5, max_single_file_bytes=5)

    with pytest.raises(RepositoryRetrievalError) as raised:
        extract_repository_archive(archive_path, destination, limits)

    assert raised.value.code == "archive_limit_exceeded"
    assert list(destination.iterdir()) == []


def test_enforces_archive_entry_limit(tmp_path: Path) -> None:
    archive_path = tmp_path / "repository.tar.gz"
    _write_archive(
        archive_path,
        {
            "owner-repository-sha/one.txt": b"one",
            "owner-repository-sha/two.txt": b"two",
        },
    )
    limits = RetrievalLimits(max_members=2)

    with pytest.raises(RepositoryRetrievalError) as raised:
        extract_repository_archive(archive_path, tmp_path / "source", limits)

    assert raised.value.code == "archive_limit_exceeded"


def test_rejects_file_and_directory_conflicts(tmp_path: Path) -> None:
    archive_path = tmp_path / "repository.tar.gz"
    _write_archive(
        archive_path,
        {
            "owner-repository-sha/src": b"file",
            "owner-repository-sha/src/app.py": b"child",
        },
    )

    with pytest.raises(RepositoryRetrievalError) as raised:
        extract_repository_archive(archive_path, tmp_path / "source", RetrievalLimits())

    assert raised.value.code == "archive_unsafe"


def test_enforces_compressed_size_when_extractor_is_used_directly(tmp_path: Path) -> None:
    archive_path = tmp_path / "repository.tar.gz"
    _write_archive(archive_path, {"owner-repository-sha/README.md": b"content"})

    with pytest.raises(RepositoryRetrievalError) as raised:
        extract_repository_archive(
            archive_path,
            tmp_path / "source",
            RetrievalLimits(max_archive_bytes=1),
        )

    assert raised.value.code == "archive_limit_exceeded"


def test_rejects_directory_entries_that_claim_file_data(tmp_path: Path) -> None:
    archive_path = tmp_path / "repository.tar.gz"
    with tarfile.open(archive_path, mode="w:gz") as archive:
        member = tarfile.TarInfo("owner-repository-sha/")
        member.type = tarfile.DIRTYPE
        member.size = 1
        archive.addfile(member)

    with pytest.raises(RepositoryRetrievalError) as raised:
        extract_repository_archive(archive_path, tmp_path / "source", RetrievalLimits())

    assert raised.value.code == "archive_unsafe"


def test_enforces_single_file_size_limit(tmp_path: Path) -> None:
    archive_path = tmp_path / "repository.tar.gz"
    _write_archive(archive_path, {"owner-repository-sha/large.txt": b"1234"})
    limits = RetrievalLimits(max_expanded_bytes=10, max_single_file_bytes=3)

    with pytest.raises(RepositoryRetrievalError) as raised:
        extract_repository_archive(archive_path, tmp_path / "source", limits)

    assert raised.value.code == "archive_limit_exceeded"


def test_enforces_path_depth_limit(tmp_path: Path) -> None:
    archive_path = tmp_path / "repository.tar.gz"
    _write_archive(archive_path, {"owner-repository-sha/a/b/file.txt": b"content"})
    limits = RetrievalLimits(max_path_depth=2)

    with pytest.raises(RepositoryRetrievalError) as raised:
        extract_repository_archive(archive_path, tmp_path / "source", limits)

    assert raised.value.code == "archive_limit_exceeded"


def test_rejects_empty_archive(tmp_path: Path) -> None:
    archive_path = tmp_path / "repository.tar.gz"
    _write_archive(archive_path, {})

    with pytest.raises(RepositoryRetrievalError) as raised:
        extract_repository_archive(archive_path, tmp_path / "source", RetrievalLimits())

    assert raised.value.code == "archive_empty"


def test_rejects_multiple_archive_roots(tmp_path: Path) -> None:
    archive_path = tmp_path / "repository.tar.gz"
    _write_archive(
        archive_path,
        {
            "owner-repository-sha/one.txt": b"one",
            "other-root/two.txt": b"two",
        },
    )

    with pytest.raises(RepositoryRetrievalError) as raised:
        extract_repository_archive(archive_path, tmp_path / "source", RetrievalLimits())

    assert raised.value.code == "archive_unsafe"


def test_rejects_hard_links(tmp_path: Path) -> None:
    archive_path = tmp_path / "repository.tar.gz"
    with tarfile.open(archive_path, mode="w:gz") as archive:
        root = tarfile.TarInfo("owner-repository-sha/")
        root.type = tarfile.DIRTYPE
        archive.addfile(root)
        link = tarfile.TarInfo("owner-repository-sha/link")
        link.type = tarfile.LNKTYPE
        link.linkname = "owner-repository-sha/target"
        archive.addfile(link)

    with pytest.raises(RepositoryRetrievalError) as raised:
        extract_repository_archive(archive_path, tmp_path / "source", RetrievalLimits())

    assert raised.value.code == "archive_unsafe"


def test_rejects_corrupt_archive(tmp_path: Path) -> None:
    archive_path = tmp_path / "repository.tar.gz"
    archive_path.write_bytes(b"not a tar archive")

    with pytest.raises(RepositoryRetrievalError) as raised:
        extract_repository_archive(archive_path, tmp_path / "source", RetrievalLimits())

    assert raised.value.code == "archive_invalid"
