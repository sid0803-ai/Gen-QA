"""Pydantic schemas for the testcases domain (project-scoped Test Case
Repository)."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domains.requirements.models import RequirementPriority
from app.domains.testcases.models import (
    ExecutionType,
    TestCaseCategory,
    TestCaseSeverity,
    TestCaseSource,
    TestCaseStatus,
    TestingLevel,
)


class TestCaseCreate(BaseModel):
    """Manual creation body - everything except id/code/test_design_id/
    source/status/timestamps, which the server sets (source="human",
    status="draft", code generated sequentially)."""

    requirement_id: uuid.UUID
    title: str = Field(min_length=1, max_length=255)
    category: TestCaseCategory
    testing_level: TestingLevel
    priority: RequirementPriority = RequirementPriority.medium
    severity: TestCaseSeverity
    preconditions: str = ""
    test_data: str = ""
    steps: list[str] = Field(default_factory=list)
    expected_result: str = ""
    business_rule: str = ""
    automation_candidate: bool = False
    # If omitted, defaults from automation_candidate (true -> automation,
    # false -> manual) at creation time - see repository.create_test_case().
    execution_type: ExecutionType | None = None
    tags: list[str] = Field(default_factory=list)


class TestCaseUpdate(BaseModel):
    """Any subset of the editable fields. Same "omitted and null both mean
    leave unchanged" convention as RequirementUpdate/ProjectUpdate - a field
    can be set to a new value but not explicitly cleared back to empty via
    this endpoint (send an empty string/list instead)."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    category: TestCaseCategory | None = None
    testing_level: TestingLevel | None = None
    priority: RequirementPriority | None = None
    severity: TestCaseSeverity | None = None
    preconditions: str | None = None
    test_data: str | None = None
    steps: list[str] | None = None
    expected_result: str | None = None
    business_rule: str | None = None
    automation_candidate: bool | None = None
    execution_type: ExecutionType | None = None
    tags: list[str] | None = None


class TestCaseRead(BaseModel):
    """Full test case detail, including steps/preconditions/test_data/
    expected_result/business_rule."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    requirement_id: uuid.UUID
    test_design_id: uuid.UUID | None
    code: str
    title: str
    category: TestCaseCategory
    testing_level: TestingLevel
    priority: RequirementPriority
    severity: TestCaseSeverity
    preconditions: str
    test_data: str
    steps: list[str]
    expected_result: str
    business_rule: str
    automation_candidate: bool
    execution_type: ExecutionType
    status: TestCaseStatus
    source: TestCaseSource
    tags: list[str]
    created_by: uuid.UUID
    created_at: datetime
    updated_by: uuid.UUID | None
    updated_at: datetime


class TestCaseListItem(BaseModel):
    """List-view shape: includes the parent requirement's title (a join) so
    the UI never needs a second round-trip per row; omits the long-form
    fields (steps/preconditions/test_data/expected_result/business_rule) -
    use the detail endpoint for those."""

    id: uuid.UUID
    code: str
    title: str
    testing_level: TestingLevel
    category: TestCaseCategory
    priority: RequirementPriority
    severity: TestCaseSeverity
    status: TestCaseStatus
    source: TestCaseSource
    automation_candidate: bool
    execution_type: ExecutionType
    requirement_id: uuid.UUID
    requirement_title: str
    tags: list[str]
    created_at: datetime


class TestCaseVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    test_case_id: uuid.UUID
    version_number: int
    snapshot: dict
    edited_by: uuid.UUID
    edited_at: datetime
