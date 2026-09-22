"""Pydantic schemas for the requirements + ai-analysis domains."""
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domains.ai.schemas import RequirementAnalysisPayload
from app.domains.requirements.models import AnalysisStatus, RequirementPriority

LatestAnalysisStatus = Literal["none", "draft", "approved", "rejected"]


class RequirementCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    business_objective: str | None = None
    acceptance_criteria: str | None = None
    priority: RequirementPriority = RequirementPriority.medium


class RequirementUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1)
    business_objective: str | None = None
    acceptance_criteria: str | None = None
    priority: RequirementPriority | None = None


class RequirementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    description: str
    business_objective: str | None
    acceptance_criteria: str | None
    priority: RequirementPriority
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


class RequirementListItem(BaseModel):
    id: uuid.UUID
    title: str
    priority: RequirementPriority
    latest_analysis_status: LatestAnalysisStatus
    created_at: datetime


class AnalysisRead(BaseModel):
    """Full analysis detail, including `payload`."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requirement_id: uuid.UUID
    status: AnalysisStatus
    payload: RequirementAnalysisPayload
    created_by: uuid.UUID
    created_at: datetime
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    updated_at: datetime


class AnalysisListItem(BaseModel):
    """List-view analysis shape: omits `payload` for brevity (see README)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requirement_id: uuid.UUID
    status: AnalysisStatus
    created_by: uuid.UUID
    created_at: datetime
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    updated_at: datetime


class AnalysisPayloadUpdate(BaseModel):
    payload: RequirementAnalysisPayload
