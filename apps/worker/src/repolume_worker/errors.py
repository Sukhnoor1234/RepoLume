"""Safe failures raised at repository retrieval and analysis boundaries."""

from repolume_worker.jobs import JobStatus


class RepositoryRetrievalError(Exception):
    """A controlled retrieval failure that is safe to record for a job."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class RepositoryAnalysisError(Exception):
    """A controlled static-analysis failure that is safe to record for a job."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class AnalysisPipelineError(Exception):
    """A controlled pipeline failure with safe lifecycle context."""

    def __init__(
        self,
        *,
        analysis_id: str,
        code: str,
        message: str,
        transitions: tuple[JobStatus, ...],
    ) -> None:
        super().__init__(message)
        self.analysis_id = analysis_id
        self.code = code
        self.message = message
        self.status = JobStatus.FAILED
        self.transitions = transitions
