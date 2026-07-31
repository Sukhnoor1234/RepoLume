"""Structured exception handlers for the HTTP boundary."""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from repolume_api.schemas import ErrorDetail, ErrorResponse


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    payload = ErrorResponse(error=ErrorDetail(code=code, message=message))
    return JSONResponse(status_code=status_code, content=payload.model_dump())


async def handle_http_exception(_request: Request, exc: HTTPException) -> JSONResponse:
    """Convert Starlette HTTP errors to the public error envelope."""

    code = "not_found" if exc.status_code == 404 else "http_error"
    message = exc.detail if isinstance(exc.detail, str) else "The request could not be completed."
    return _error_response(exc.status_code, code, message)


async def handle_validation_error(_request: Request, _exc: RequestValidationError) -> JSONResponse:
    """Return a stable validation error without echoing submitted values."""

    return _error_response(422, "validation_error", "Request validation failed.")
