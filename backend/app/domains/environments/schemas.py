"""Pydantic schemas for the environments domain."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EnvironmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    base_url: str = Field(min_length=1, max_length=2048)
    variables: dict[str, str] = Field(default_factory=dict)


class EnvironmentUpdate(BaseModel):
    """Any subset of the editable fields. Same "omitted and null both mean
    leave unchanged" convention as every other PATCH in this codebase -
    `variables` can be replaced wholesale but not explicitly cleared back to
    `{}` via `null` (send `{}` instead)."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    base_url: str | None = Field(default=None, min_length=1, max_length=2048)
    variables: dict[str, str] | None = None


class EnvironmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    base_url: str
    variables: dict[str, str]
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
