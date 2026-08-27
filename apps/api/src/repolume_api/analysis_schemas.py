"""Public request and response models for repository analysis jobs."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

AnalysisStatus = Literal["queued", "cloning", "analyzing", "completed", "failed"]
Confidence = Literal["confirmed", "heuristic"]
NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(ge=1)]
SymbolKind = Literal[
    "function",
    "async_function",
    "class",
    "variable",
    "interface",
    "type_alias",
    "enum",
]
EvidenceNodeKind = Literal["module", "symbol", "entry_point"]


class StrictModel(BaseModel):
    """Reject undocumented fields at application boundaries."""

    model_config = ConfigDict(extra="forbid")


class AnalysisSubmissionRequest(StrictModel):
    """Repository reference submitted for background analysis."""

    repository_url: str = Field(min_length=1, max_length=2048)
    ref: str | None = Field(default=None, min_length=1, max_length=255)


class AnalysisSubmissionResponse(StrictModel):
    """Accepted analysis job identity."""

    analysis_id: str
    status: Literal["queued"]


class AnalysisRepositoryResponse(StrictModel):
    """Normalized repository associated with an analysis job."""

    provider: Literal["github"] = "github"
    owner: str
    repository: str
    canonical_url: str
    ref: str | None


class AnalysisFailureResponse(StrictModel):
    """Safe terminal failure details for a job."""

    code: str
    message: str


class AnalysisStatusResponse(StrictModel):
    """Current state of one analysis job."""

    analysis_id: str
    status: AnalysisStatus
    repository: AnalysisRepositoryResponse
    result_available: bool
    failure: AnalysisFailureResponse | None = None


class SourceLocationResponse(StrictModel):
    """Repository-relative evidence location."""

    path: str
    line: PositiveInt
    end_line: PositiveInt


class ArchitectureNodeResponse(StrictModel):
    """One node in the language-neutral repository graph."""

    id: str
    kind: Literal[
        "repository",
        "module",
        "symbol",
        "entry_point",
        "external_dependency",
    ]
    name: str
    language: str | None
    location: SourceLocationResponse | None = None
    qualified_name: str | None = None
    symbol_kind: SymbolKind | None = None
    detail: str | None = None
    confidence: Confidence | None = None
    decorators: list[str] = Field(default_factory=list)
    source_bytes: NonNegativeInt | None = None
    line_count: NonNegativeInt | None = None


class ArchitectureEdgeResponse(StrictModel):
    """One directed relationship in the repository graph."""

    id: str
    kind: Literal["contains", "depends_on"]
    source: str
    target: str
    confidence: Confidence
    location: SourceLocationResponse


class ArchitectureDiagnosticResponse(StrictModel):
    """Non-fatal analyzer diagnostic safe for API clients."""

    language: str
    code: str
    message: str
    path: str
    line: PositiveInt | None = None


class ArchitectureSummaryResponse(StrictModel):
    """Graph counts used by status displays and explorer summaries."""

    language_count: NonNegativeInt
    node_count: NonNegativeInt
    edge_count: NonNegativeInt
    module_count: NonNegativeInt
    symbol_count: NonNegativeInt
    entry_point_count: NonNegativeInt
    external_dependency_count: NonNegativeInt
    dependency_count: NonNegativeInt
    diagnostic_count: NonNegativeInt


class RepositoryArchitectureResponse(StrictModel):
    """Versioned language-neutral architecture returned for a completed job."""

    schema_version: str
    languages: list[str]
    nodes: list[ArchitectureNodeResponse]
    edges: list[ArchitectureEdgeResponse]
    diagnostics: list[ArchitectureDiagnosticResponse]
    summary: ArchitectureSummaryResponse


class EvidenceQueryRequest(StrictModel):
    """Bounded natural-language query over one completed architecture."""

    question: str = Field(min_length=3, max_length=300)
    limit: int = Field(default=5, ge=1, le=10)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        """Trim boundary whitespace while rejecting effectively empty questions."""

        normalized = value.strip()
        if len(normalized) < 3:
            raise ValueError("question must contain at least 3 visible characters")
        return normalized


class EvidenceMatchResponse(StrictModel):
    """One explainable source match used by future answer generation."""

    node_id: str
    kind: EvidenceNodeKind
    name: str
    language: str | None
    location: SourceLocationResponse
    confidence: Confidence
    score: PositiveInt
    matched_terms: list[str]
    relationship_count: NonNegativeInt


class EvidenceQueryResponse(StrictModel):
    """Ranked evidence for a repository question, without generated prose."""

    schema_version: Literal["1.0"] = "1.0"
    question: str
    matches: list[EvidenceMatchResponse]
