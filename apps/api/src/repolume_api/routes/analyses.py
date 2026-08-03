"""Repository analysis submission and inspection routes."""

from typing import Annotated, NoReturn

from fastapi import APIRouter, Path, Request, status

from repolume_api.analyses import (
    AnalysisJobService,
    AnalysisJobSnapshot,
    AnalysisNotCompleted,
    AnalysisNotFound,
    AnalysisServiceUnavailable,
)
from repolume_api.analysis_schemas import (
    AnalysisFailureResponse,
    AnalysisRepositoryResponse,
    AnalysisStatusResponse,
    AnalysisSubmissionRequest,
    AnalysisSubmissionResponse,
    RepositoryArchitectureResponse,
)
from repolume_api.errors import APIError
from repolume_api.repositories import RepositoryReferenceError, normalize_repository_reference
from repolume_api.schemas import ErrorResponse

router = APIRouter(prefix="/v1/analyses", tags=["analyses"])
AnalysisId = Annotated[str, Path(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]


def _service(request: Request) -> AnalysisJobService:
    return request.app.state.analysis_job_service


def _raise_service_error(error: Exception) -> NoReturn:
    if isinstance(error, AnalysisServiceUnavailable):
        raise APIError(
            status_code=503,
            code="analysis_service_unavailable",
            message="Repository analysis is temporarily unavailable.",
        ) from error
    if isinstance(error, AnalysisNotFound):
        raise APIError(
            status_code=404,
            code="analysis_not_found",
            message="The requested analysis was not found.",
        ) from error
    if isinstance(error, AnalysisNotCompleted):
        raise APIError(
            status_code=409,
            code="analysis_not_completed",
            message="Architecture is available only after analysis completes.",
        ) from error
    raise error


def _repository_response(snapshot: AnalysisJobSnapshot) -> AnalysisRepositoryResponse:
    repository = snapshot.repository
    return AnalysisRepositoryResponse(
        owner=repository.owner,
        repository=repository.repository,
        canonical_url=repository.canonical_url,
        ref=repository.ref,
    )


@router.post(
    "",
    response_model=AnalysisSubmissionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        422: {"model": ErrorResponse, "description": "Repository reference rejected"},
        503: {"model": ErrorResponse, "description": "Analysis service unavailable"},
    },
    summary="Submit a repository analysis",
)
async def submit_analysis(
    payload: AnalysisSubmissionRequest,
    request: Request,
) -> AnalysisSubmissionResponse:
    """Validate a repository reference and submit it to the job-service boundary."""

    try:
        repository = normalize_repository_reference(payload.repository_url, payload.ref)
    except RepositoryReferenceError as exc:
        raise APIError(status_code=422, code=exc.code, message=exc.message) from exc

    try:
        snapshot = _service(request).submit(repository)
    except (AnalysisServiceUnavailable, AnalysisNotFound, AnalysisNotCompleted) as exc:
        _raise_service_error(exc)

    if snapshot.status != "queued":
        raise RuntimeError("The analysis service returned a non-queued submission")
    return AnalysisSubmissionResponse(analysis_id=snapshot.analysis_id, status="queued")


@router.get(
    "/{analysis_id}",
    response_model=AnalysisStatusResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Analysis not found"},
        503: {"model": ErrorResponse, "description": "Analysis service unavailable"},
    },
    summary="Inspect an analysis job",
)
async def inspect_analysis(analysis_id: AnalysisId, request: Request) -> AnalysisStatusResponse:
    """Return safe lifecycle state without embedding the complete architecture."""

    try:
        snapshot = _service(request).get(analysis_id)
    except (AnalysisServiceUnavailable, AnalysisNotFound, AnalysisNotCompleted) as exc:
        _raise_service_error(exc)

    failure = None
    if snapshot.failure_code is not None and snapshot.failure_message is not None:
        failure = AnalysisFailureResponse(
            code=snapshot.failure_code,
            message=snapshot.failure_message,
        )
    return AnalysisStatusResponse(
        analysis_id=snapshot.analysis_id,
        status=snapshot.status,
        repository=_repository_response(snapshot),
        result_available=snapshot.result_available,
        failure=failure,
    )


@router.get(
    "/{analysis_id}/architecture",
    response_model=RepositoryArchitectureResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Analysis not found"},
        409: {"model": ErrorResponse, "description": "Analysis not completed"},
        503: {"model": ErrorResponse, "description": "Analysis service unavailable"},
    },
    summary="Get completed repository architecture",
)
async def get_analysis_architecture(
    analysis_id: AnalysisId,
    request: Request,
) -> RepositoryArchitectureResponse:
    """Return a completed language-neutral repository graph."""

    try:
        return _service(request).get_architecture(analysis_id)
    except (AnalysisServiceUnavailable, AnalysisNotFound, AnalysisNotCompleted) as exc:
        _raise_service_error(exc)
