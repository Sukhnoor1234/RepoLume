"""Request and response models for repository intake."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RepositoryPreflightRequest(BaseModel):
    """Repository reference submitted for local validation."""

    model_config = ConfigDict(extra="forbid")

    repository_url: str = Field(min_length=1, max_length=2048)
    ref: str | None = Field(default=None, min_length=1, max_length=255)


class RepositoryPreflightResponse(BaseModel):
    """Normalized repository reference accepted by the intake boundary."""

    provider: Literal["github"] = "github"
    owner: str
    repository: str
    canonical_url: str
    ref: str | None
