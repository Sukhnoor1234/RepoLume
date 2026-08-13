"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from repolume_api import __version__
from repolume_api.analyses import AnalysisJobService, UnavailableAnalysisJobService
from repolume_api.analysis_runtime import AnalysisRuntime, create_analysis_runtime
from repolume_api.config import Settings
from repolume_api.errors import (
    APIError,
    handle_api_error,
    handle_http_exception,
    handle_validation_error,
)
from repolume_api.routes.analyses import router as analyses_router
from repolume_api.routes.health import router as health_router
from repolume_api.routes.repositories import router as repositories_router


def create_app(
    settings: Settings | None = None,
    *,
    analysis_job_service: AnalysisJobService | None = None,
    analysis_runtime: AnalysisRuntime | None = None,
) -> FastAPI:
    """Create an API instance with explicit runtime configuration."""

    configured_settings = settings or Settings.from_environment()
    if analysis_job_service is not None and analysis_runtime is not None:
        raise ValueError("Provide either analysis_job_service or analysis_runtime, not both")
    configured_runtime = analysis_runtime
    if (
        configured_runtime is None
        and analysis_job_service is None
        and configured_settings.analysis_runtime_enabled
    ):
        configured_runtime = create_analysis_runtime()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if configured_runtime is not None:
            configured_runtime.start()
        try:
            yield
        finally:
            if configured_runtime is not None:
                configured_runtime.stop()

    app = FastAPI(
        title="RepoLume API",
        description="HTTP boundary for the RepoLume architecture explorer.",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.settings = configured_settings
    app.state.analysis_runtime = configured_runtime
    app.state.analysis_job_service = (
        analysis_job_service
        or (configured_runtime.service if configured_runtime is not None else None)
        or UnavailableAnalysisJobService()
    )
    app.add_exception_handler(APIError, handle_api_error)
    app.add_exception_handler(HTTPException, handle_http_exception)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.include_router(health_router)
    app.include_router(repositories_router)
    app.include_router(analyses_router)
    return app


app = create_app()
