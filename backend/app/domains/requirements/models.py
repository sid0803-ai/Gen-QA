"""Requirement, AIAnalysis, FeasibilityStudy and TestStrategy models
(requirements domain).

AIAnalysis (Sprint 2) and FeasibilityStudy/TestStrategy (Sprint 3) all live
here rather than in `app.domains.ai` because their *lifecycle*
(draft/approve/reject, edit-while-draft, history of multiple records per
requirement) is a requirements-domain concern tied 1:1 to a Requirement's own
persistence and access control - same precedent as AIAnalysis. The `ai`
domain only supplies the generated *content* (via `AIService`/`AIProvider`)
used to populate a new draft row of any of these three - it has no database
model of its own.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.domains.identity.models import User  # noqa: F401 (registers User on the shared registry)
from app.domains.projects.models import Project  # noqa: F401 (registers Project on the shared registry)


class RequirementPriority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class AnalysisStatus(str, enum.Enum):
    draft = "draft"
    approved = "approved"
    rejected = "rejected"


class FeasibilityStatus(str, enum.Enum):
    draft = "draft"
    approved = "approved"
    rejected = "rejected"


class StrategyStatus(str, enum.Enum):
    draft = "draft"
    approved = "approved"
    rejected = "rejected"


class TestDesignStatus(str, enum.Enum):
    draft = "draft"
    approved = "approved"
    rejected = "rejected"


class Requirement(Base):
    __tablename__ = "requirements"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    business_objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    acceptance_criteria: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[RequirementPriority] = mapped_column(
        SAEnum(
            RequirementPriority,
            name="requirement_priority",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=RequirementPriority.medium,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    analyses: Mapped[list["AIAnalysis"]] = relationship(
        "AIAnalysis", back_populates="requirement", cascade="all, delete-orphan"
    )
    feasibility_studies: Mapped[list["FeasibilityStudy"]] = relationship(
        "FeasibilityStudy", back_populates="requirement", cascade="all, delete-orphan"
    )
    test_strategies: Mapped[list["TestStrategy"]] = relationship(
        "TestStrategy", back_populates="requirement", cascade="all, delete-orphan"
    )
    test_designs: Mapped[list["TestDesign"]] = relationship(
        "TestDesign", back_populates="requirement", cascade="all, delete-orphan"
    )


class AIAnalysis(Base):
    __tablename__ = "ai_analyses"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[AnalysisStatus] = mapped_column(
        SAEnum(
            AnalysisStatus, name="analysis_status", values_callable=lambda e: [m.value for m in e]
        ),
        nullable=False,
        default=AnalysisStatus.draft,
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # DB-generated, strictly-increasing, internal-only ordering key. `id` is a
    # random UUID (no ordering signal) and `created_at` can collide between
    # two analyses created in quick succession (timestamp resolution), which
    # would make "most recent analysis" queries pick a row non-deterministically.
    # This column is never exposed via the API - it exists purely so
    # repository.py can order/rank "latest first" correctly.
    sequence: Mapped[int] = mapped_column(BigInteger, Identity(always=True), nullable=False, unique=True)

    requirement: Mapped["Requirement"] = relationship("Requirement", back_populates="analyses")


class FeasibilityStudy(Base):
    __tablename__ = "feasibility_studies"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[FeasibilityStatus] = mapped_column(
        SAEnum(
            FeasibilityStatus,
            name="feasibility_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=FeasibilityStatus.draft,
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Same monotonic-ordering trick as AIAnalysis.sequence - see that column's
    # docstring for why `created_at` alone is not safe to order/rank by.
    sequence: Mapped[int] = mapped_column(BigInteger, Identity(always=True), nullable=False, unique=True)

    requirement: Mapped["Requirement"] = relationship("Requirement", back_populates="feasibility_studies")


class TestStrategy(Base):
    __tablename__ = "test_strategies"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[StrategyStatus] = mapped_column(
        SAEnum(
            StrategyStatus, name="strategy_status", values_callable=lambda e: [m.value for m in e]
        ),
        nullable=False,
        default=StrategyStatus.draft,
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Same monotonic-ordering trick as AIAnalysis.sequence - see that column's
    # docstring for why `created_at` alone is not safe to order/rank by.
    sequence: Mapped[int] = mapped_column(BigInteger, Identity(always=True), nullable=False, unique=True)

    requirement: Mapped["Requirement"] = relationship("Requirement", back_populates="test_strategies")


class TestDesign(Base):
    """Sprint 4: the fourth "AI suggests, human reviews, human approves"
    stage on a requirement, same draft/approved/rejected shape as
    AIAnalysis/FeasibilityStudy/TestStrategy. `payload` validates against
    `app.domains.ai.schemas.TestDesignPayload` (a summary + list of
    TestDesignScenario, each with an `include` flag). Approving a
    TestDesign promotes every scenario with `include == True` into a
    permanent `TestCase` row in the project-wide Test Case Repository
    (`app.domains.testcases`) - see
    `app.domains.requirements.service.approve_test_design()`.
    """

    __tablename__ = "test_designs"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[TestDesignStatus] = mapped_column(
        SAEnum(
            TestDesignStatus, name="test_design_status", values_callable=lambda e: [m.value for m in e]
        ),
        nullable=False,
        default=TestDesignStatus.draft,
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Same monotonic-ordering trick as AIAnalysis.sequence, added proactively
    # this sprint (Sprints 2 and 3 each had to discover the need for this the
    # hard way on their own new tables) - see that column's docstring for why
    # `created_at` alone is not safe to order/rank "most recent" by.
    sequence: Mapped[int] = mapped_column(BigInteger, Identity(always=True), nullable=False, unique=True)

    requirement: Mapped["Requirement"] = relationship("Requirement", back_populates="test_designs")
