"""Shared API response models."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response returned when the API is ready to accept requests."""

    status: Literal["ok"] = "ok"
    service: str
    version: str
    environment: str


class ErrorDetail(BaseModel):
    """Machine-readable API error information."""

    code: str
    message: str


class ErrorResponse(BaseModel):
    """Consistent envelope for framework and application errors."""

    error: ErrorDetail
