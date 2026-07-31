"""Service health routes."""

from fastapi import APIRouter, Request

from repolume_api import __version__
from repolume_api.config import Settings
from repolume_api.schemas import HealthResponse

router = APIRouter(tags=["system"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check API health",
)
async def health(request: Request) -> HealthResponse:
    """Report whether the API process is accepting requests."""

    settings: Settings = request.app.state.settings
    return HealthResponse(
        service=settings.service_name,
        version=__version__,
        environment=settings.environment,
    )
