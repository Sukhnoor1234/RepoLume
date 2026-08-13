"""Tests for the end-to-end repository analysis pipeline."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from repolume_worker.analysis_models import PythonAnalysisArtifact
from repolume_worker.architecture_models import ArchitectureNodeKind
from repolume_worker.errors import (
    AnalysisPipelineError,
    RepositoryAnalysisError,
    RepositoryRetrievalError,
)
from repolume_worker.jobs import AnalysisJob, InvalidJobTransition, JobStatus
from repolume_worker.pipeline import RepositoryAnalysisPipeline
from repolume_worker.retrieval import RepositoryRequest, RetrievedRepository

_FIXTURE = Path(__file__).parent / "fixtures" / "mixed_repository"
_COMMIT_SHA = "a" * 40


class FakeRetriever:
    def __init__(
        self,
        source_path: Path = _FIXTURE,
        *,
        retrieval_error: RepositoryRetrievalError | None = None,
        cleanup_error: RepositoryRetrievalError | None = None,
    ) -> None:
        self.source_path = source_path
        self.retrieval_error = retrieval_error
        self.cleanup_error = cleanup_error
        self.requests: list[RepositoryRequest] = []
        self.active = False
        self.exit_count = 0

    @contextmanager
    def retrieve(self, request: RepositoryRequest) -> Iterator[RetrievedRepository]:
        self.requests.append(request)
        if self.retrieval_error is not None:
            raise self.retrieval_error

        self.active = True
        try:
            yield RetrievedRepository(
                owner=request.owner,
                repository=request.repository,
                requested_ref=request.ref,
                commit_sha=_COMMIT_SHA,
                source_path=self.source_path,
                file_count=5,
                expanded_bytes=321,
            )
        finally:
            self.active = False
            self.exit_count += 1
            if self.cleanup_error is not None:
                raise self.cleanup_error


class FailingPythonAnalyzer:
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.calls = 0

    def analyze(self, _repository_root: Path) -> PythonAnalysisArtifact:
        self.calls += 1
        raise self.error


class UnreachedScriptAnalyzer:
    def __init__(self) -> None:
        self.calls = 0

    def analyze(self, _repository_root: Path):
        self.calls += 1
        raise AssertionError("The script analyzer should not have been called.")


class InvalidComposer:
    def compose(self, _artifacts):
        raise ValueError("dangling internal graph details")


def _job() -> AnalysisJob:
    return AnalysisJob("analysis-123")


def _request() -> RepositoryRequest:
    return RepositoryRequest("octocat", "Hello-World", "feature/parser")


def test_runs_complete_pipeline_and_cleans_up_before_returning() -> None:
    retriever = FakeRetriever()

    result = RepositoryAnalysisPipeline(retriever).run(_job(), _request())

    assert result.schema_version == "1.0"
    assert result.analysis_id == "analysis-123"
    assert result.status is JobStatus.COMPLETED
    assert result.transitions == (
        JobStatus.QUEUED,
        JobStatus.CLONING,
        JobStatus.ANALYZING,
        JobStatus.COMPLETED,
    )
    assert result.repository.provider == "github"
    assert result.repository.owner == "octocat"
    assert result.repository.repository == "Hello-World"
    assert result.repository.requested_ref == "feature/parser"
    assert result.repository.commit_sha == _COMMIT_SHA
    assert result.repository.file_count == 5
    assert result.repository.expanded_bytes == 321
    assert result.architecture.summary.node_count == 13
    assert result.architecture.summary.edge_count == 14
    assert not retriever.active
    assert retriever.exit_count == 1


def test_forwards_normalized_repository_request() -> None:
    retriever = FakeRetriever()
    request = _request()

    RepositoryAnalysisPipeline(retriever).run(_job(), request)

    assert retriever.requests == [request]


def test_result_json_is_stable_and_excludes_temporary_source_path() -> None:
    first = RepositoryAnalysisPipeline(FakeRetriever()).run(_job(), _request())
    second = RepositoryAnalysisPipeline(FakeRetriever()).run(_job(), _request())

    first_json = first.to_json()

    assert first_json == second.to_json()
    assert str(_FIXTURE.resolve()) not in first_json
    assert '"status": "completed"' in first_json
    assert _COMMIT_SHA in first_json


def test_architecture_remains_available_after_retrieval_context_exits() -> None:
    retriever = FakeRetriever()

    result = RepositoryAnalysisPipeline(retriever).run(_job(), _request())
    module_names = {
        node.name for node in result.architecture.nodes if node.kind is ArchitectureNodeKind.MODULE
    }

    assert not retriever.active
    assert module_names == {
        "backend.app",
        "backend.service",
        "frontend.app",
        "frontend.service",
    }


def test_preserves_safe_retrieval_failure_and_failed_lifecycle() -> None:
    retriever = FakeRetriever(
        retrieval_error=RepositoryRetrievalError(
            "repository_not_found",
            "The GitHub repository or ref was not found.",
        )
    )

    with pytest.raises(AnalysisPipelineError) as raised:
        RepositoryAnalysisPipeline(retriever).run(_job(), _request())

    assert raised.value.code == "repository_not_found"
    assert raised.value.message == "The GitHub repository or ref was not found."
    assert raised.value.analysis_id == "analysis-123"
    assert raised.value.status is JobStatus.FAILED
    assert raised.value.transitions == (
        JobStatus.QUEUED,
        JobStatus.CLONING,
        JobStatus.FAILED,
    )


def test_analysis_failure_exits_retrieval_and_skips_later_analyzers() -> None:
    retriever = FakeRetriever()
    python_analyzer = FailingPythonAnalyzer(
        RepositoryAnalysisError(
            "analysis_limit_exceeded",
            "The repository contains more source than can be analyzed.",
        )
    )
    script_analyzer = UnreachedScriptAnalyzer()

    with pytest.raises(AnalysisPipelineError) as raised:
        RepositoryAnalysisPipeline(
            retriever,
            python_analyzer=python_analyzer,
            script_analyzer=script_analyzer,
        ).run(_job(), _request())

    assert raised.value.code == "analysis_limit_exceeded"
    assert raised.value.transitions == (
        JobStatus.QUEUED,
        JobStatus.CLONING,
        JobStatus.ANALYZING,
        JobStatus.FAILED,
    )
    assert python_analyzer.calls == 1
    assert script_analyzer.calls == 0
    assert not retriever.active
    assert retriever.exit_count == 1


def test_maps_unexpected_failures_without_leaking_details() -> None:
    retriever = FakeRetriever()
    analyzer = FailingPythonAnalyzer(RuntimeError("secret internal parser details"))

    with pytest.raises(AnalysisPipelineError) as raised:
        RepositoryAnalysisPipeline(
            retriever,
            python_analyzer=analyzer,
        ).run(_job(), _request())

    assert raised.value.code == "analysis_failed"
    assert raised.value.message == "Repository analysis could not be completed."
    assert "secret" not in raised.value.message
    assert isinstance(raised.value.__cause__, RuntimeError)
    assert raised.value.transitions[-1] is JobStatus.FAILED
    assert not retriever.active


def test_maps_invalid_composition_to_safe_failure() -> None:
    retriever = FakeRetriever()

    with pytest.raises(AnalysisPipelineError) as raised:
        RepositoryAnalysisPipeline(
            retriever,
            composer=InvalidComposer(),
        ).run(_job(), _request())

    assert raised.value.code == "architecture_composition_failed"
    assert raised.value.message == "Repository architecture could not be composed."
    assert "dangling" not in raised.value.message
    assert raised.value.transitions[-2:] == (
        JobStatus.ANALYZING,
        JobStatus.FAILED,
    )
    assert not retriever.active


def test_cleanup_failure_prevents_completed_status() -> None:
    retriever = FakeRetriever(
        cleanup_error=RepositoryRetrievalError(
            "repository_cleanup_failed",
            "Temporary repository files could not be removed.",
        )
    )

    with pytest.raises(AnalysisPipelineError) as raised:
        RepositoryAnalysisPipeline(retriever).run(_job(), _request())

    assert raised.value.code == "repository_cleanup_failed"
    assert raised.value.transitions == (
        JobStatus.QUEUED,
        JobStatus.CLONING,
        JobStatus.ANALYZING,
        JobStatus.FAILED,
    )
    assert JobStatus.COMPLETED not in raised.value.transitions
    assert not retriever.active
    assert retriever.exit_count == 1


def test_requires_a_queued_job_before_retrieval() -> None:
    retriever = FakeRetriever()
    job = AnalysisJob("analysis-123", JobStatus.ANALYZING)

    with pytest.raises(InvalidJobTransition):
        RepositoryAnalysisPipeline(retriever).run(job, _request())

    assert retriever.requests == []


def test_empty_repository_completes_with_root_only(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Empty repository\n", encoding="utf-8")
    retriever = FakeRetriever(tmp_path)

    result = RepositoryAnalysisPipeline(retriever).run(_job(), _request())

    assert result.status is JobStatus.COMPLETED
    assert result.architecture.languages == ()
    assert [node.id for node in result.architecture.nodes] == ["repository"]
    assert result.architecture.edges == ()


class RecordingLifecycleObserver:
    def __init__(self) -> None:
        self.events: list[tuple[str, str | None]] = []

    def on_cloning(self) -> None:
        self.events.append(("cloning", None))

    def on_analyzing(self, commit_sha: str) -> None:
        self.events.append(("analyzing", commit_sha))


def test_notifies_lifecycle_observer_before_analysis() -> None:
    observer = RecordingLifecycleObserver()

    result = RepositoryAnalysisPipeline(FakeRetriever()).run(
        _job(),
        _request(),
        observer=observer,
    )

    assert result.status is JobStatus.COMPLETED
    assert observer.events == [("cloning", None), ("analyzing", _COMMIT_SHA)]
