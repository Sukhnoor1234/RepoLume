"""Resource limits for untrusted repository archives and source analysis."""

from dataclasses import dataclass

MEBIBYTE = 1024 * 1024


@dataclass(frozen=True, slots=True)
class RetrievalLimits:
    """Limits enforced before and during repository extraction."""

    max_archive_bytes: int = 50 * MEBIBYTE
    max_expanded_bytes: int = 250 * MEBIBYTE
    max_single_file_bytes: int = 20 * MEBIBYTE
    max_members: int = 25_000
    max_path_depth: int = 50
    max_path_length: int = 512

    def __post_init__(self) -> None:
        for field_name in self.__dataclass_fields__:
            if getattr(self, field_name) <= 0:
                raise ValueError(f"{field_name} must be greater than zero")

        if self.max_single_file_bytes > self.max_expanded_bytes:
            raise ValueError("max_single_file_bytes cannot exceed max_expanded_bytes")


@dataclass(frozen=True, slots=True)
class AnalysisLimits:
    """Limits applied while reading untrusted Python source as data."""

    max_python_files: int = 5_000
    max_total_source_bytes: int = 50 * MEBIBYTE
    max_single_source_bytes: int = 2 * MEBIBYTE
    max_path_depth: int = 50
    max_path_length: int = 512

    def __post_init__(self) -> None:
        for field_name in self.__dataclass_fields__:
            if getattr(self, field_name) <= 0:
                raise ValueError(f"{field_name} must be greater than zero")

        if self.max_single_source_bytes > self.max_total_source_bytes:
            raise ValueError("max_single_source_bytes cannot exceed max_total_source_bytes")


@dataclass(frozen=True, slots=True)
class ScriptAnalysisLimits:
    """Limits applied while reading untrusted TypeScript and JavaScript."""

    max_script_files: int = 5_000
    max_total_source_bytes: int = 50 * MEBIBYTE
    max_single_source_bytes: int = 2 * MEBIBYTE
    max_path_depth: int = 50
    max_path_length: int = 512

    def __post_init__(self) -> None:
        for field_name in self.__dataclass_fields__:
            if getattr(self, field_name) <= 0:
                raise ValueError(f"{field_name} must be greater than zero")

        if self.max_single_source_bytes > self.max_total_source_bytes:
            raise ValueError("max_single_source_bytes cannot exceed max_total_source_bytes")
