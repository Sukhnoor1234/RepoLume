import pytest

from repolume_worker.jobs import AnalysisJob, InvalidJobTransition, JobStatus


def test_job_follows_successful_lifecycle() -> None:
    job = AnalysisJob(analysis_id="analysis-123")

    job = job.transition_to(JobStatus.CLONING)
    job = job.transition_to(JobStatus.ANALYZING)
    job = job.transition_to(JobStatus.COMPLETED)

    assert job.status is JobStatus.COMPLETED
    assert job.status.is_terminal


def test_job_can_fail_from_active_state() -> None:
    job = AnalysisJob(analysis_id="analysis-123", status=JobStatus.ANALYZING)

    failed_job = job.transition_to(JobStatus.FAILED)

    assert failed_job.status is JobStatus.FAILED
    assert failed_job.status.is_terminal


def test_job_cannot_skip_lifecycle_state() -> None:
    job = AnalysisJob(analysis_id="analysis-123")

    with pytest.raises(InvalidJobTransition, match="queued to completed"):
        job.transition_to(JobStatus.COMPLETED)


def test_job_requires_an_identifier() -> None:
    with pytest.raises(ValueError, match="analysis_id"):
        AnalysisJob(analysis_id=" ")


def test_job_normalizes_serialized_statuses() -> None:
    job = AnalysisJob(analysis_id="analysis-123", status="queued")

    analyzing_job = job.transition_to("cloning").transition_to("analyzing")

    assert job.status is JobStatus.QUEUED
    assert analyzing_job.status is JobStatus.ANALYZING


def test_job_rejects_unknown_status() -> None:
    with pytest.raises(ValueError, match="Unknown analysis job status"):
        AnalysisJob(analysis_id="analysis-123", status="unknown")
