"""Stable contracts returned by the end-to-end repository analysis pipeline."""

import json
from dataclasses import asdict, dataclass

from repolume_worker.architecture_models import RepositoryArchitectureArtifact
from repolume_worker.jobs import JobStatus


@dataclass(frozen=True, slots=True)
class RepositorySnapshotIdentity:
    """Immutable repository coordinates retained after temporary cleanup."""

    provider: str
    owner: str
    repository: str
    requested_ref: str | None
    commit_sha: str
    file_count: int
    expanded_bytes: int


@dataclass(frozen=True, slots=True)
class AnalysisPipelineResult:
    """Completed analysis metadata and its language-neutral architecture."""

    schema_version: str
    analysis_id: str
    status: JobStatus
    transitions: tuple[JobStatus, ...]
    repository: RepositorySnapshotIdentity
    architecture: RepositoryArchitectureArtifact

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible representation of the completed result."""

        return asdict(self)

    def to_json(self) -> str:
        """Serialize without temporary paths or process-specific values."""

        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"
