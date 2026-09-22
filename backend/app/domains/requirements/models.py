"""Requirement and AIAnalysis models (requirements domain).

AIAnalysis lives here rather than in `app.domains.ai` because the analysis
*lifecycle* (draft/approve/reject, edit-while-draft, history of multiple
analyses per requirement) is a requirements-domain concern tied 1:1 to a
Requirement's own persistence and access control. The `ai` domain only
supplies the analysis *content* (via `AIService`/`AIProvider`) used to
populate a new AIAnalysis row - it has no database model of its own.
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
