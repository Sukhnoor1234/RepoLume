"""Repository intake routes."""

from fastapi import APIRouter

from repolume_api.errors import APIError
from repolume_api.repositories import RepositoryReferenceError, normalize_repository_reference
from repolume_api.repository_schemas import RepositoryPreflightRequest, RepositoryPreflightResponse
from repolume_api.schemas import ErrorResponse

router = APIRouter(prefix="/v1/repositories", tags=["repositories"])


@router.post(
    "/preflight",
    response_model=RepositoryPreflightResponse,
    responses={422: {"model": ErrorResponse, "description": "Repository reference rejected"}},
    summary="Validate a repository reference",
)
async def preflight_repository(
    request: RepositoryPreflightRequest,
) -> RepositoryPreflightResponse:
    """Validate and normalize input without contacting the repository host."""

    try:
        reference = normalize_repository_reference(request.repository_url, request.ref)
    except RepositoryReferenceError as exc:
        raise APIError(status_code=422, code=exc.code, message=exc.message) from exc

    return RepositoryPreflightResponse(
        owner=reference.owner,
        repository=reference.repository,
        canonical_url=reference.canonical_url,
        ref=reference.ref,
    )
