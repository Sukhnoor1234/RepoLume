"""Safe failures raised at repository retrieval and analysis boundaries."""


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
