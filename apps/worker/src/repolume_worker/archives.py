"""Inspection and extraction of untrusted GitHub tar archives."""

import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from repolume_worker.errors import RepositoryRetrievalError
from repolume_worker.limits import RetrievalLimits

_COPY_CHUNK_BYTES = 64 * 1024
_WINDOWS_INVALID_CHARACTERS = frozenset('<>:"|?*')
_WINDOWS_RESERVED_NAMES = frozenset(
    {"con", "prn", "aux", "nul"}
    | {f"com{number}" for number in range(1, 10)}
    | {f"lpt{number}" for number in range(1, 10)}
)


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    """Measured contents of an extracted repository archive."""

    file_count: int
    expanded_bytes: int


@dataclass(frozen=True, slots=True)
class _ArchiveEntry:
    member: tarfile.TarInfo
    relative_parts: tuple[str, ...]

    @property
    def collision_key(self) -> tuple[str, ...]:
        return tuple(part.casefold() for part in self.relative_parts)


def _archive_error(message: str) -> RepositoryRetrievalError:
    return RepositoryRetrievalError("archive_unsafe", message)


def _validate_component(component: str) -> None:
    if (
        not component
        or component in {".", ".."}
        or len(component) > 255
        or component.endswith((" ", "."))
        or any(character in _WINDOWS_INVALID_CHARACTERS for character in component)
        or any(ord(character) < 32 or ord(character) == 127 for character in component)
    ):
        raise _archive_error("The repository archive contains an unsafe path.")

    reserved_name = component.split(".", maxsplit=1)[0].casefold()
    if reserved_name in _WINDOWS_RESERVED_NAMES:
        raise _archive_error("The repository archive contains an unsupported path.")


def _member_parts(member: tarfile.TarInfo, limits: RetrievalLimits) -> tuple[str, ...]:
    name = member.name
    if not name or name.startswith("/") or "\\" in name or "\0" in name:
        raise _archive_error("The repository archive contains an unsafe path.")

    trimmed_name = name[:-1] if name.endswith("/") else name
    parts = tuple(trimmed_name.split("/"))
    for component in parts:
        _validate_component(component)

    if len(parts) < 1:
        raise _archive_error("The repository archive contains an unsafe path.")

    relative_parts = parts[1:]
    relative_path = "/".join(relative_parts)
    if len(relative_parts) > limits.max_path_depth or len(relative_path) > limits.max_path_length:
        raise RepositoryRetrievalError(
            "archive_limit_exceeded",
            "The repository archive contains paths beyond the supported limits.",
        )
    return parts


def _inspect_archive(
    archive: tarfile.TarFile,
    limits: RetrievalLimits,
) -> tuple[list[_ArchiveEntry], ExtractionResult]:
    entries: list[_ArchiveEntry] = []
    seen_paths: set[tuple[str, ...]] = set()
    file_paths: set[tuple[str, ...]] = set()
    archive_root: str | None = None
    expanded_bytes = 0
    file_count = 0

    for member_count, member in enumerate(archive, start=1):
        if member_count > limits.max_members:
            raise RepositoryRetrievalError(
                "archive_limit_exceeded",
                "The repository archive contains too many entries.",
            )
        if not (member.isdir() or member.isfile()):
            raise _archive_error("The repository archive contains links or special files.")
        if member.isdir() and member.size != 0:
            raise _archive_error("The repository archive contains an invalid directory.")

        parts = _member_parts(member, limits)
        if archive_root is None:
            archive_root = parts[0]
        elif parts[0] != archive_root:
            raise _archive_error("The repository archive contains multiple root directories.")

        relative_parts = parts[1:]
        if not relative_parts:
            if member.isfile():
                raise _archive_error("The repository archive root must be a directory.")
            continue

        entry = _ArchiveEntry(member=member, relative_parts=relative_parts)
        if entry.collision_key in seen_paths:
            raise _archive_error("The repository archive contains duplicate paths.")
        seen_paths.add(entry.collision_key)

        if member.isfile():
            if member.size < 0 or member.size > limits.max_single_file_bytes:
                raise RepositoryRetrievalError(
                    "archive_limit_exceeded",
                    "The repository archive contains a file beyond the supported limit.",
                )
            expanded_bytes += member.size
            file_count += 1
            if expanded_bytes > limits.max_expanded_bytes:
                raise RepositoryRetrievalError(
                    "archive_limit_exceeded",
                    "The expanded repository is beyond the supported size limit.",
                )
            file_paths.add(entry.collision_key)

        entries.append(entry)

    if file_count == 0:
        raise RepositoryRetrievalError("archive_empty", "The repository archive contains no files.")

    for entry in entries:
        for depth in range(1, len(entry.collision_key)):
            if entry.collision_key[:depth] in file_paths:
                raise _archive_error("The repository archive contains conflicting paths.")

    return entries, ExtractionResult(file_count=file_count, expanded_bytes=expanded_bytes)


def _copy_file(source: BinaryIO, target: Path, expected_bytes: int) -> None:
    remaining = expected_bytes
    with target.open("xb") as output:
        while remaining:
            chunk = source.read(min(_COPY_CHUNK_BYTES, remaining))
            if not chunk:
                raise _archive_error("The repository archive ended unexpectedly.")
            output.write(chunk)
            remaining -= len(chunk)


def extract_repository_archive(
    archive_path: Path,
    destination: Path,
    limits: RetrievalLimits,
) -> ExtractionResult:
    """Inspect an entire tarball, then extract regular files without metadata."""

    try:
        if archive_path.stat().st_size > limits.max_archive_bytes:
            raise RepositoryRetrievalError(
                "archive_limit_exceeded",
                "The compressed repository is beyond the supported size limit.",
            )
        destination.mkdir(parents=True, exist_ok=False)
        with tarfile.open(archive_path, mode="r:gz") as archive:
            entries, result = _inspect_archive(archive, limits)
            for entry in entries:
                target = destination.joinpath(*entry.relative_parts)
                if entry.member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue

                target.parent.mkdir(parents=True, exist_ok=True)
                source = archive.extractfile(entry.member)
                if source is None:
                    raise _archive_error("The repository archive contains an unreadable file.")
                with source:
                    _copy_file(source, target, entry.member.size)
            return result
    except RepositoryRetrievalError:
        raise
    except (OSError, tarfile.TarError) as exc:
        raise RepositoryRetrievalError(
            "archive_invalid",
            "The repository archive could not be safely extracted.",
        ) from exc
