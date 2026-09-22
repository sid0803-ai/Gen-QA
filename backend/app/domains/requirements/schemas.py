"""Pydantic schemas for the requirements + ai-analysis + feasibility +
test-strategy domains."""
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domains.ai.schemas import (
    FeasibilityStudyPayload,
    RequirementAnalysisPayload,
    TestDesignPayload,
    TestStrategyPayload,
)
from app.domains.requirements.models import (
    AnalysisStatus,
    FeasibilityStatus,
    RequirementPriority,
    StrategyStatus,
    TestDesignStatus,
)

LatestAnalysisStatus = Literal["none", "draft", "approved", "rejected"]
# Same "none"|"draft"|"approved"|"rejected" semantics as LatestAnalysisStatus,
# just named per-domain for readability at call sites.
LatestFeasibilityStatus = Literal["none", "draft", "approved", "rejected"]
LatestStrategyStatus = Literal["none", "draft", "approved", "rejected"]
LatestTestDesignStatus = Literal["none", "draft", "approved", "rejected"]


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
    # Sprint 3: not an ORM column - the router always builds this schema with
    # these two fields set explicitly (no default) from
    # repository.get_requirement_latest_statuses() / the equivalent freshly
    # computed after create/update, so a call site can never forget to
    # compute them and silently ship a stale/wrong "none".
    latest_feasibility_status: LatestFeasibilityStatus
    latest_strategy_status: LatestStrategyStatus
    latest_test_design_status: LatestTestDesignStatus


class RequirementListItem(BaseModel):
    id: uuid.UUID
    title: str
    priority: RequirementPriority
    latest_analysis_status: LatestAnalysisStatus
    latest_feasibility_status: LatestFeasibilityStatus
    latest_strategy_status: LatestStrategyStatus
    latest_test_design_status: LatestTestDesignStatus
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


class FeasibilityRead(BaseModel):
    """Full feasibility study detail, including `payload`."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requirement_id: uuid.UUID
    status: FeasibilityStatus
    payload: FeasibilityStudyPayload
    created_by: uuid.UUID
    created_at: datetime
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    updated_at: datetime


class FeasibilityListItem(BaseModel):
    """List-view feasibility shape: omits `payload` for brevity (see README)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requirement_id: uuid.UUID
    status: FeasibilityStatus
    created_by: uuid.UUID
    created_at: datetime
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    updated_at: datetime


class FeasibilityPayloadUpdate(BaseModel):
    payload: FeasibilityStudyPayload


class StrategyRead(BaseModel):
    """Full test strategy detail, including `payload`."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requirement_id: uuid.UUID
    status: StrategyStatus
    payload: TestStrategyPayload
    created_by: uuid.UUID
    created_at: datetime
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    updated_at: datetime


class StrategyListItem(BaseModel):
    """List-view test strategy shape: omits `payload` for brevity (see README)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requirement_id: uuid.UUID
    status: StrategyStatus
    created_by: uuid.UUID
    created_at: datetime
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    updated_at: datetime


class StrategyPayloadUpdate(BaseModel):
    payload: TestStrategyPayload


class TestDesignCreate(BaseModel):
    scope: Literal["api", "ui", "both"] = "both"


class TestDesignRead(BaseModel):
    """Full test design detail, including `payload`."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requirement_id: uuid.UUID
    status: TestDesignStatus
    payload: TestDesignPayload
    created_by: uuid.UUID
    created_at: datetime
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    updated_at: datetime


class TestDesignListItem(BaseModel):
    """List-view test design shape: omits `payload` for brevity (see README)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requirement_id: uuid.UUID
    status: TestDesignStatus
    created_by: uuid.UUID
    created_at: datetime
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    updated_at: datetime


class TestDesignPayloadUpdate(BaseModel):
    payload: TestDesignPayload


class TestDesignApproveResponse(TestDesignRead):
    """Same shape as TestDesignRead (the approved test design itself), plus
    the ids of every TestCase promoted from this approval (one per
    `include == true` scenario in the payload) and their count, so the
    frontend can react (e.g. navigate to/highlight the newly created test
    cases) without a second round-trip to the Test Case Repository.
    `created_test_case_count == len(created_test_case_ids)` always; both are
    provided since a caller may only need one or the other."""

    created_test_case_ids: list[uuid.UUID]
    created_test_case_count: int
