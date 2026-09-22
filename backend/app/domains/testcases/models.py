"""TestCase, TestCaseVersion and TestCaseCounter models (testcases domain).

Project-scoped Test Case Repository: independent of the requirements
domain's TestDesign draft/approve/reject lifecycle (`app.domains.requirements`).
A TestCase either:
  - is promoted from an approved TestDesign scenario (`source="ai"`,
    `test_design_id` set, created already `status="approved"` - see
    `app.domains.requirements.service.approve_test_design()`), or
  - is created directly by a human (`source="human"`, `test_design_id`
    null, created `status="draft"`).

Every edit to a test case's editable fields creates a `TestCaseVersion`
snapshot (see `repository.update_test_case`), so the full edit history is
retained even though the TestCase row itself only ever holds the current
state.

`priority` reuses `app.domains.requirements.models.RequirementPriority`
(same Postgres enum type, `requirement_priority`) rather than defining a
second, parallel priority enum - "priority" means the same thing everywhere
in this system.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.domains.identity.models import User  # noqa: F401 (registers User on the shared registry)
from app.domains.projects.models import Project  # noqa: F401 (registers Project on the shared registry)
from app.domains.requirements.models import Requirement, RequirementPriority  # noqa: F401


class TestCaseCategory(str, enum.Enum):
    positive = "positive"
    negative = "negative"
    boundary = "boundary"
    edge_case = "edge_case"
    business_logic = "business_logic"
    validation = "validation"
    security = "security"
    performance = "performance"
    regression = "regression"


class TestingLevel(str, enum.Enum):
    functional = "functional"
    api = "api"
    ui = "ui"
    integration = "integration"
    security = "security"
    performance = "performance"
    regression = "regression"


class TestCaseSeverity(str, enum.Enum):
    minor = "minor"
    major = "major"
    critical = "critical"
    blocker = "blocker"


class ExecutionType(str, enum.Enum):
    manual = "manual"
    automation = "automation"
    hybrid = "hybrid"


class TestCaseStatus(str, enum.Enum):
    # No "rejected": a human who doesn't want a draft test case simply
    # deletes it (DELETE /test-cases/{id}) - see README.
    draft = "draft"
    approved = "approved"


class TestCaseSource(str, enum.Enum):
    ai = "ai"
    human = "human"


class TestCaseCounter(Base):
    """Per-project sequential counter backing TestCase.code generation
    ('TC-001', 'TC-002', ...). See repository._next_code() for the
    concurrency-safety approach (a row-level lock via SELECT ... FOR UPDATE,
    taken inside the same transaction as the TestCase insert that follows)."""

    __tablename__ = "test_case_counters"

    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    next_value: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)


class TestCase(Base):
    __tablename__ = "test_cases"
    __table_args__ = (
        UniqueConstraint("project_id", "code", name="uq_test_case_project_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    # Required, not nullable: traceability is a core product invariant -
    # every test case traces to exactly one requirement, whether it was
    # promoted from that requirement's Test Design or authored manually
    # against it.
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False
    )
    # Null for manually-created test cases; set for ones promoted from an
    # approved TestDesign scenario.
    test_design_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("test_designs.id", ondelete="SET NULL"), nullable=True
    )
    # e.g. "TC-001", sequential and unique per project - see
    # repository._next_code() for the concurrency-safe generation approach.
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[TestCaseCategory] = mapped_column(
        SAEnum(
            TestCaseCategory, name="test_case_category", values_callable=lambda e: [m.value for m in e]
        ),
        nullable=False,
    )
    testing_level: Mapped[TestingLevel] = mapped_column(
        SAEnum(TestingLevel, name="testing_level", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    priority: Mapped[RequirementPriority] = mapped_column(
        SAEnum(
            RequirementPriority, name="requirement_priority", values_callable=lambda e: [m.value for m in e]
        ),
        nullable=False,
    )
    severity: Mapped[TestCaseSeverity] = mapped_column(
        SAEnum(
            TestCaseSeverity, name="test_case_severity", values_callable=lambda e: [m.value for m in e]
        ),
        nullable=False,
    )
    preconditions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    test_data: Mapped[str] = mapped_column(Text, nullable=False, default="")
    steps: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    expected_result: Mapped[str] = mapped_column(Text, nullable=False, default="")
    business_rule: Mapped[str] = mapped_column(Text, nullable=False, default="")
    automation_candidate: Mapped[bool] = mapped_column(nullable=False, default=False)
    # Human-editable; defaults from automation_candidate at creation time
    # (true -> automation, false -> manual) but can diverge afterward.
    execution_type: Mapped[ExecutionType] = mapped_column(
        SAEnum(ExecutionType, name="execution_type", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    status: Mapped[TestCaseStatus] = mapped_column(
        SAEnum(
            TestCaseStatus, name="test_case_status", values_callable=lambda e: [m.value for m in e]
        ),
        nullable=False,
        default=TestCaseStatus.draft,
    )
    source: Mapped[TestCaseSource] = mapped_column(
        SAEnum(
            TestCaseSource, name="test_case_source", values_callable=lambda e: [m.value for m in e]
        ),
        nullable=False,
    )
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_by: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Same monotonic-ordering trick as AIAnalysis.sequence (requirements
    # domain) - `id` is a random UUID (no ordering signal) and `created_at`
    # can collide between two test cases created in quick succession
    # (timestamp resolution). Used to order "newest first" deterministically.
    sequence: Mapped[int] = mapped_column(BigInteger, Identity(always=True), nullable=False, unique=True)

    versions: Mapped[list["TestCaseVersion"]] = relationship(
        "TestCaseVersion", back_populates="test_case", cascade="all, delete-orphan"
    )


class TestCaseVersion(Base):
    """One immutable snapshot of a TestCase's editable fields, taken after
    each PATCH is applied. version_number starts at 1 and increments per
    test case, so the ordered list of versions reads as "what it looked
    like at each point," most recent last."""

    __tablename__ = "test_case_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    test_case_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    edited_by: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    edited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    test_case: Mapped["TestCase"] = relationship("TestCase", back_populates="versions")
