"""Analysis job lifecycle contracts."""

from dataclasses import dataclass, replace
from enum import StrEnum


class JobStatus(StrEnum):
    """States shared by the API contract and analysis worker."""

    QUEUED = "queued"
    CLONING = "cloning"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"

    @property
    def is_terminal(self) -> bool:
        return self in {JobStatus.COMPLETED, JobStatus.FAILED}


ALLOWED_TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.QUEUED: frozenset({JobStatus.CLONING, JobStatus.FAILED}),
    JobStatus.CLONING: frozenset({JobStatus.ANALYZING, JobStatus.FAILED}),
    JobStatus.ANALYZING: frozenset({JobStatus.COMPLETED, JobStatus.FAILED}),
    JobStatus.COMPLETED: frozenset(),
    JobStatus.FAILED: frozenset(),
}


class InvalidJobTransition(ValueError):
    """Raised when a job attempts to skip or leave a lifecycle state."""


def _coerce_status(status: JobStatus | str) -> JobStatus:
    try:
        return JobStatus(status)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Unknown analysis job status: {status!r}") from error


@dataclass(frozen=True, slots=True)
class AnalysisJob:
    """Minimal immutable job state used at the worker boundary."""

    analysis_id: str
    status: JobStatus = JobStatus.QUEUED

    def __post_init__(self) -> None:
        if not self.analysis_id.strip():
            raise ValueError("analysis_id must not be empty")
        object.__setattr__(self, "status", _coerce_status(self.status))

    def transition_to(self, next_status: JobStatus | str) -> "AnalysisJob":
        """Return a new job state when the transition is allowed."""

        normalized_status = _coerce_status(next_status)
        if normalized_status not in ALLOWED_TRANSITIONS[self.status]:
            raise InvalidJobTransition(
                f"Cannot transition analysis job from {self.status} to {normalized_status}"
            )
        return replace(self, status=normalized_status)
