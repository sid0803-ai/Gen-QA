"""Data-access layer for the requirements + ai-analysis domains.

CRITICAL ISOLATION RULE (same as `app.domains.projects.repository`): every
function here that reads or writes a Requirement/AIAnalysis takes
`project_id` + the requesting user's id and enforces membership (and, where
relevant, a minimum role) via `project_repository.require_membership` before
touching any row. Requirement rows are additionally always filtered by
`project_id`, so a requirement id from another project can never be reached
even if guessed.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.projects import repository as project_repository
from app.domains.projects.models import ProjectRole
from app.domains.requirements.models import AIAnalysis, AnalysisStatus, Requirement, RequirementPriority


class RequirementNotFoundError(Exception):
    """Requirement doesn't exist in this project (or the project doesn't -> 404)."""


class AnalysisNotFoundError(Exception):
    """Analysis doesn't exist for this requirement -> 404."""


class AnalysisNotDraftError(Exception):
    """Analysis is not in 'draft' status, so this operation is not allowed -> 409."""


async def _get_requirement_row(
    db: AsyncSession, project_id: uuid.UUID, requirement_id: uuid.UUID
) -> Requirement | None:
    stmt = select(Requirement).where(
        Requirement.id == requirement_id, Requirement.project_id == project_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _get_analysis_row(
    db: AsyncSession, requirement_id: uuid.UUID, analysis_id: uuid.UUID
) -> AIAnalysis | None:
    stmt = select(AIAnalysis).where(
        AIAnalysis.id == analysis_id, AIAnalysis.requirement_id == requirement_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# --- Requirements ------------------------------------------------------


async def create_requirement(
    db: AsyncSession,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    title: str,
    description: str,
    business_objective: str | None,
    acceptance_criteria: str | None,
    priority: RequirementPriority,
) -> Requirement:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.member)

    requirement = Requirement(
        project_id=project_id,
        title=title,
        description=description,
        business_objective=business_objective,
        acceptance_criteria=acceptance_criteria,
        priority=priority,
        created_by=user_id,
    )
    db.add(requirement)
    await db.commit()
    await db.refresh(requirement)
    return requirement


async def list_requirements(
    db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID
) -> list[tuple[Requirement, str]]:
    """Returns (requirement, latest_analysis_status) pairs, newest requirement
    first. latest_analysis_status is "none" if the requirement has never been
    analyzed, else the status of its most recently created AIAnalysis."""
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.viewer)

    latest_analysis = (
        select(
            AIAnalysis.requirement_id,
            AIAnalysis.status,
            func.row_number()
            .over(partition_by=AIAnalysis.requirement_id, order_by=AIAnalysis.sequence.desc())
            .label("rn"),
        )
    ).subquery()

    stmt = (
        select(Requirement, latest_analysis.c.status)
        .outerjoin(
            latest_analysis,
            (latest_analysis.c.requirement_id == Requirement.id) & (latest_analysis.c.rn == 1),
        )
        .where(Requirement.project_id == project_id)
        .order_by(Requirement.created_at.desc())
    )
    result = await db.execute(stmt)
    return [
        (requirement, status_value.value if status_value is not None else "none")
        for requirement, status_value in result.all()
    ]


async def get_requirement(
    db: AsyncSession, project_id: uuid.UUID, requirement_id: uuid.UUID, user_id: uuid.UUID
) -> Requirement:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.viewer)
    requirement = await _get_requirement_row(db, project_id, requirement_id)
    if requirement is None:
        raise RequirementNotFoundError()
    return requirement


async def update_requirement(
    db: AsyncSession,
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    title: str | None = None,
    description: str | None = None,
    business_objective: str | None = None,
    acceptance_criteria: str | None = None,
    priority: RequirementPriority | None = None,
) -> Requirement:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.member)
    requirement = await _get_requirement_row(db, project_id, requirement_id)
    if requirement is None:
        raise RequirementNotFoundError()

    if title is not None:
        requirement.title = title
    if description is not None:
        requirement.description = description
    if business_objective is not None:
        requirement.business_objective = business_objective
    if acceptance_criteria is not None:
        requirement.acceptance_criteria = acceptance_criteria
    if priority is not None:
        requirement.priority = priority

    await db.commit()
    await db.refresh(requirement)
    return requirement


async def delete_requirement(
    db: AsyncSession, project_id: uuid.UUID, requirement_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.admin)
    requirement = await _get_requirement_row(db, project_id, requirement_id)
    if requirement is None:
        raise RequirementNotFoundError()

    await db.delete(requirement)
    await db.commit()


# --- AI Analyses ---------------------------------------------------------


async def create_analysis(
    db: AsyncSession,
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: dict,
) -> AIAnalysis:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.member)
    requirement = await _get_requirement_row(db, project_id, requirement_id)
    if requirement is None:
        raise RequirementNotFoundError()

    analysis = AIAnalysis(
        requirement_id=requirement.id,
        status=AnalysisStatus.draft,
        payload=payload,
        created_by=user_id,
    )
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)
    return analysis


async def list_analyses(
    db: AsyncSession, project_id: uuid.UUID, requirement_id: uuid.UUID, user_id: uuid.UUID
) -> list[AIAnalysis]:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.viewer)
    requirement = await _get_requirement_row(db, project_id, requirement_id)
    if requirement is None:
        raise RequirementNotFoundError()

    stmt = (
        select(AIAnalysis)
        .where(AIAnalysis.requirement_id == requirement_id)
        .order_by(AIAnalysis.sequence.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_analysis(
    db: AsyncSession,
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    analysis_id: uuid.UUID,
    user_id: uuid.UUID,
) -> AIAnalysis:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.viewer)
    requirement = await _get_requirement_row(db, project_id, requirement_id)
    if requirement is None:
        raise RequirementNotFoundError()

    analysis = await _get_analysis_row(db, requirement_id, analysis_id)
    if analysis is None:
        raise AnalysisNotFoundError()
    return analysis


async def update_analysis_payload(
    db: AsyncSession,
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    analysis_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: dict,
) -> AIAnalysis:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.member)
    requirement = await _get_requirement_row(db, project_id, requirement_id)
    if requirement is None:
        raise RequirementNotFoundError()

    analysis = await _get_analysis_row(db, requirement_id, analysis_id)
    if analysis is None:
        raise AnalysisNotFoundError()
    if analysis.status != AnalysisStatus.draft:
        raise AnalysisNotDraftError()

    analysis.payload = payload
    await db.commit()
    await db.refresh(analysis)
    return analysis


async def approve_analysis(
    db: AsyncSession,
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    analysis_id: uuid.UUID,
    user_id: uuid.UUID,
) -> AIAnalysis:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.member)
    requirement = await _get_requirement_row(db, project_id, requirement_id)
    if requirement is None:
        raise RequirementNotFoundError()

    analysis = await _get_analysis_row(db, requirement_id, analysis_id)
    if analysis is None:
        raise AnalysisNotFoundError()
    if analysis.status != AnalysisStatus.draft:
        raise AnalysisNotDraftError()

    analysis.status = AnalysisStatus.approved
    analysis.approved_by = user_id
    analysis.approved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(analysis)
    return analysis


async def reject_analysis(
    db: AsyncSession,
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    analysis_id: uuid.UUID,
    user_id: uuid.UUID,
) -> AIAnalysis:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.member)
    requirement = await _get_requirement_row(db, project_id, requirement_id)
    if requirement is None:
        raise RequirementNotFoundError()

    analysis = await _get_analysis_row(db, requirement_id, analysis_id)
    if analysis is None:
        raise AnalysisNotFoundError()
    if analysis.status != AnalysisStatus.draft:
        raise AnalysisNotDraftError()

    analysis.status = AnalysisStatus.rejected
    await db.commit()
    await db.refresh(analysis)
    return analysis
