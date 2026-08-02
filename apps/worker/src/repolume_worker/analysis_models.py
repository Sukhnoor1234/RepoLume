"""Stable output contracts shared by source-language analyzers."""

import json
from dataclasses import asdict, dataclass
from enum import StrEnum


class Confidence(StrEnum):
    """How strongly source evidence supports an analysis result."""

    CONFIRMED = "confirmed"
    HEURISTIC = "heuristic"


class DependencyKind(StrEnum):
    """Whether an imported module exists inside the analyzed snapshot."""

    LOCAL = "local"
    EXTERNAL = "external"


class SymbolKind(StrEnum):
    """Top-level Python declarations exposed by the first analyzer."""

    FUNCTION = "function"
    ASYNC_FUNCTION = "async_function"
    CLASS = "class"


@dataclass(frozen=True, slots=True)
class SourceLocation:
    """A repository-relative source range used as evidence."""

    path: str
    line: int
    end_line: int


@dataclass(frozen=True, slots=True)
class Symbol:
    """A top-level declaration found in a module."""

    name: str
    qualified_name: str
    kind: SymbolKind
    location: SourceLocation
    decorators: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PythonModule:
    """A parsed Python file and the declarations it owns."""

    name: str
    path: str
    source_bytes: int
    line_count: int
    symbols: tuple[Symbol, ...]


@dataclass(frozen=True, slots=True)
class Dependency:
    """A directed import relationship originating in a Python module."""

    source: str
    target: str
    kind: DependencyKind
    confidence: Confidence
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class EntryPoint:
    """A confirmed or likely place where execution begins."""

    module: str
    kind: str
    confidence: Confidence
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class AnalysisDiagnostic:
    """A non-fatal source problem that prevented complete analysis."""

    code: str
    message: str
    path: str
    line: int | None = None


@dataclass(frozen=True, slots=True)
class AnalysisSummary:
    """Small counts suitable for status and portfolio displays."""

    module_count: int
    symbol_count: int
    local_dependency_count: int
    external_dependency_count: int
    entry_point_count: int
    diagnostic_count: int


@dataclass(frozen=True, slots=True)
class PythonAnalysisArtifact:
    """Deterministic v1 artifact produced without executing repository code."""

    schema_version: str
    language: str
    modules: tuple[PythonModule, ...]
    dependencies: tuple[Dependency, ...]
    entry_points: tuple[EntryPoint, ...]
    diagnostics: tuple[AnalysisDiagnostic, ...]
    summary: AnalysisSummary

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible representation of the artifact."""

        return asdict(self)

    def to_json(self) -> str:
        """Serialize with stable ordering for snapshots and future persistence."""

        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"
