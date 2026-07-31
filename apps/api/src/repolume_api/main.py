"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from repolume_api import __version__
from repolume_api.config import Settings
from repolume_api.errors import handle_http_exception, handle_validation_error
from repolume_api.routes.health import router as health_router


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create an API instance with explicit runtime configuration."""

    app = FastAPI(
        title="RepoLume API",
        description="HTTP boundary for the RepoLume architecture explorer.",
        version=__version__,
    )
    app.state.settings = settings or Settings.from_environment()
    app.add_exception_handler(HTTPException, handle_http_exception)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.include_router(health_router)
    return app


app = create_app()
