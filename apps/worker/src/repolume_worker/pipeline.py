"""End-to-end orchestration for one isolated repository analysis."""

from collections.abc import Iterable
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Protocol

from repolume_worker.analysis_models import (
    PythonAnalysisArtifact,
    ScriptAnalysisArtifact,
)
from repolume_worker.architecture import RepositoryArchitectureComposer
from repolume_worker.architecture_models import RepositoryArchitectureArtifact
from repolume_worker.errors import (
    AnalysisPipelineError,
    RepositoryAnalysisError,
    RepositoryRetrievalError,
)
from repolume_worker.jobs import AnalysisJob, JobStatus
from repolume_worker.pipeline_models import (
    AnalysisPipelineResult,
    RepositorySnapshotIdentity,
)
from repolume_worker.python_analysis import PythonRepositoryAnalyzer
from repolume_worker.retrieval import RepositoryRequest, RetrievedRepository
from repolume_worker.typescript_analysis import TypeScriptRepositoryAnalyzer

_PIPELINE_SCHEMA_VERSION = "1.0"


class RepositoryRetriever(Protocol):
    """Retrieval boundary required by the pipeline."""

    def retrieve(
        self,
        request: RepositoryRequest,
    ) -> AbstractContextManager[RetrievedRepository]: ...


class PythonAnalyzer(Protocol):
    """Python analysis boundary required by the pipeline."""

    def analyze(self, repository_root: Path) -> PythonAnalysisArtifact: ...


class ScriptAnalyzer(Protocol):
    """TypeScript and JavaScript analysis boundary required by the pipeline."""

    def analyze(self, repository_root: Path) -> ScriptAnalysisArtifact: ...


class ArchitectureComposer(Protocol):
    """Architecture composition boundary required by the pipeline."""

    def compose(
        self,
        artifacts: Iterable[PythonAnalysisArtifact | ScriptAnalysisArtifact],
    ) -> RepositoryArchitectureArtifact: ...


class PipelineLifecycleError(RuntimeError):
    """Base error raised when durable lifecycle observation cannot continue."""


class PipelineStateConflict(PipelineLifecycleError):
    """Raised when another delivery already advanced the durable job."""


class PipelineStateUnavailable(PipelineLifecycleError):
    """Raised when lifecycle persistence is temporarily unavailable."""


class PipelineLifecycleObserver(Protocol):
    """Durable active-state callbacks emitted before expensive analysis work."""

    def on_cloning(self) -> None: ...

    def on_analyzing(self, commit_sha: str) -> None: ...


class RepositoryAnalysisPipeline:
    """Run retrieval, source analysis, composition, and cleanup in order."""

    def __init__(
        self,
        retriever: RepositoryRetriever,
        *,
        python_analyzer: PythonAnalyzer | None = None,
        script_analyzer: ScriptAnalyzer | None = None,
        composer: ArchitectureComposer | None = None,
    ) -> None:
        self._retriever = retriever
        self._python_analyzer = python_analyzer or PythonRepositoryAnalyzer()
        self._script_analyzer = script_analyzer or TypeScriptRepositoryAnalyzer()
        self._composer = composer or RepositoryArchitectureComposer()

    @staticmethod
    def _transition(
        job: AnalysisJob,
        status: JobStatus,
        history: list[JobStatus],
    ) -> AnalysisJob:
        transitioned = job.transition_to(status)
        history.append(transitioned.status)
        return transitioned

    @staticmethod
    def _failure(
        job: AnalysisJob,
        history: list[JobStatus],
        code: str,
        message: str,
    ) -> AnalysisPipelineError:
        failed = RepositoryAnalysisPipeline._transition(job, JobStatus.FAILED, history)
        return AnalysisPipelineError(
            analysis_id=failed.analysis_id,
            code=code,
            message=message,
            transitions=tuple(history),
        )

    def run(
        self,
        job: AnalysisJob,
        request: RepositoryRequest,
        *,
        observer: PipelineLifecycleObserver | None = None,
    ) -> AnalysisPipelineResult:
        """Run one queued job and return only after temporary cleanup succeeds."""

        history = [job.status]
        current = self._transition(job, JobStatus.CLONING, history)
        if observer is not None:
            observer.on_cloning()

        try:
            with self._retriever.retrieve(request) as repository:
                current = self._transition(current, JobStatus.ANALYZING, history)
                if observer is not None:
                    observer.on_analyzing(repository.commit_sha)
                python_artifact = self._python_analyzer.analyze(repository.source_path)
                script_artifact = self._script_analyzer.analyze(repository.source_path)
                try:
                    architecture = self._composer.compose((python_artifact, script_artifact))
                except ValueError as exc:
                    raise RepositoryAnalysisError(
                        "architecture_composition_failed",
                        "Repository architecture could not be composed.",
                    ) from exc

                snapshot = RepositorySnapshotIdentity(
                    provider="github",
                    owner=repository.owner,
                    repository=repository.repository,
                    requested_ref=repository.requested_ref,
                    commit_sha=repository.commit_sha,
                    file_count=repository.file_count,
                    expanded_bytes=repository.expanded_bytes,
                )
        except PipelineLifecycleError:
            raise
        except (RepositoryRetrievalError, RepositoryAnalysisError) as exc:
            raise self._failure(
                current,
                history,
                exc.code,
                exc.message,
            ) from exc
        except Exception as exc:
            raise self._failure(
                current,
                history,
                "analysis_failed",
                "Repository analysis could not be completed.",
            ) from exc

        current = self._transition(current, JobStatus.COMPLETED, history)
        return AnalysisPipelineResult(
            schema_version=_PIPELINE_SCHEMA_VERSION,
            analysis_id=current.analysis_id,
            status=current.status,
            transitions=tuple(history),
            repository=snapshot,
            architecture=architecture,
        )
