"""Language-neutral graph contracts for repository architecture artifacts."""

import json
from dataclasses import asdict, dataclass
from enum import StrEnum

from repolume_worker.analysis_models import Confidence, SourceLocation, SymbolKind


class ArchitectureNodeKind(StrEnum):
    """Kinds of nodes exposed by the repository architecture graph."""

    REPOSITORY = "repository"
    MODULE = "module"
    SYMBOL = "symbol"
    ENTRY_POINT = "entry_point"
    EXTERNAL_DEPENDENCY = "external_dependency"


class ArchitectureEdgeKind(StrEnum):
    """Kinds of directed relationships in the architecture graph."""

    CONTAINS = "contains"
    DEPENDS_ON = "depends_on"


@dataclass(frozen=True, slots=True)
class ArchitectureNode:
    """One deterministic repository or dependency graph node."""

    id: str
    kind: ArchitectureNodeKind
    name: str
    language: str | None
    location: SourceLocation | None = None
    qualified_name: str | None = None
    symbol_kind: SymbolKind | None = None
    detail: str | None = None
    confidence: Confidence | None = None
    decorators: tuple[str, ...] = ()
    source_bytes: int | None = None
    line_count: int | None = None


@dataclass(frozen=True, slots=True)
class ArchitectureEdge:
    """A directed, evidence-backed relationship between graph nodes."""

    id: str
    kind: ArchitectureEdgeKind
    source: str
    target: str
    confidence: Confidence
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class ArchitectureDiagnostic:
    """A source analyzer diagnostic with its language boundary preserved."""

    language: str
    code: str
    message: str
    path: str
    line: int | None = None


@dataclass(frozen=True, slots=True)
class ArchitectureSummary:
    """Counts suitable for API status and future graph displays."""

    language_count: int
    node_count: int
    edge_count: int
    module_count: int
    symbol_count: int
    entry_point_count: int
    external_dependency_count: int
    dependency_count: int
    diagnostic_count: int


@dataclass(frozen=True, slots=True)
class RepositoryArchitectureArtifact:
    """Deterministic language-neutral graph composed from source artifacts."""

    schema_version: str
    languages: tuple[str, ...]
    nodes: tuple[ArchitectureNode, ...]
    edges: tuple[ArchitectureEdge, ...]
    diagnostics: tuple[ArchitectureDiagnostic, ...]
    summary: ArchitectureSummary

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible representation of the graph."""

        return asdict(self)

    def to_json(self) -> str:
        """Serialize with stable ordering for snapshots and persistence."""

        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"
