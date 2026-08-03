"""Application boundary for submitting and inspecting analysis jobs."""

from dataclasses import dataclass
from typing import NoReturn, Protocol

from repolume_api.analysis_schemas import AnalysisStatus, RepositoryArchitectureResponse
from repolume_api.repositories import RepositoryReference

_ANALYSIS_STATUSES = frozenset({"queued", "cloning", "analyzing", "completed", "failed"})


class AnalysisServiceUnavailable(RuntimeError):
    """Raised when no durable job service is configured."""


class AnalysisNotFound(LookupError):
    """Raised when an analysis identifier does not exist."""


class AnalysisNotCompleted(RuntimeError):
    """Raised when architecture is requested before successful completion."""


@dataclass(frozen=True, slots=True)
class AnalysisJobSnapshot:
    """Service-level state returned without exposing storage details."""

    analysis_id: str
    status: AnalysisStatus
    repository: RepositoryReference
    result_available: bool = False
    failure_code: str | None = None
    failure_message: str | None = None

    def __post_init__(self) -> None:
        if not self.analysis_id.strip():
            raise ValueError("analysis_id must not be empty")
        if self.status not in _ANALYSIS_STATUSES:
            raise ValueError(f"unknown analysis status: {self.status!r}")
        failure_fields = (self.failure_code, self.failure_message)
        has_partial_failure = any(value is None for value in failure_fields) != all(
            value is None for value in failure_fields
        )
        if has_partial_failure:
            raise ValueError("failure code and message must be provided together")
        if self.status == "failed" and self.failure_code is None:
            raise ValueError("failed analyses require safe failure details")
        if self.status != "failed" and self.failure_code is not None:
            raise ValueError("only failed analyses may include failure details")
        if self.result_available != (self.status == "completed"):
            raise ValueError("result availability must match completed status")


class AnalysisJobService(Protocol):
    """Queue and persistence boundary required by the HTTP routes."""

    def submit(self, repository: RepositoryReference) -> AnalysisJobSnapshot: ...

    def get(self, analysis_id: str) -> AnalysisJobSnapshot: ...

    def get_architecture(self, analysis_id: str) -> RepositoryArchitectureResponse: ...


class UnavailableAnalysisJobService:
    """Safe default used until a real queue and persistence adapter is installed."""

    @staticmethod
    def _raise() -> NoReturn:
        raise AnalysisServiceUnavailable

    def submit(self, _repository: RepositoryReference) -> AnalysisJobSnapshot:
        self._raise()

    def get(self, _analysis_id: str) -> AnalysisJobSnapshot:
        self._raise()

    def get_architecture(self, _analysis_id: str) -> RepositoryArchitectureResponse:
        self._raise()
