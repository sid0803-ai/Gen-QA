"""Data-access layer for the requirements + ai-analysis + feasibility +
test-strategy domains.

CRITICAL ISOLATION RULE (same as `app.domains.projects.repository`): every
function here that reads or writes a Requirement/AIAnalysis/FeasibilityStudy/
TestStrategy takes `project_id` + the requesting user's id and enforces
membership (and, where relevant, a minimum role) via
`project_repository.require_membership` before touching any row. Requirement
rows are additionally always filtered by `project_id`, so a requirement id
from another project can never be reached even if guessed.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.projects import repository as project_repository
from app.domains.projects.models import ProjectRole
from app.domains.requirements.models import (
    AIAnalysis,
    AnalysisStatus,
    FeasibilityStatus,
    FeasibilityStudy,
    Requirement,
    RequirementPriority,
    StrategyStatus,
    TestStrategy,
)


class RequirementNotFoundError(Exception):
    """Requirement doesn't exist in this project (or the project doesn't -> 404)."""


class AnalysisNotFoundError(Exception):
    """Analysis doesn't exist for this requirement -> 404."""


class AnalysisNotDraftError(Exception):
    """Analysis is not in 'draft' status, so this operation is not allowed -> 409."""


class FeasibilityNotFoundError(Exception):
    """Feasibility study doesn't exist for this requirement -> 404."""


class FeasibilityNotDraftError(Exception):
    """Feasibility study is not in 'draft' status, so this operation is not allowed -> 409."""


class StrategyNotFoundError(Exception):
    """Test strategy doesn't exist for this requirement -> 404."""


class StrategyNotDraftError(Exception):
    """Test strategy is not in 'draft' status, so this operation is not allowed -> 409."""


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


async def _get_feasibility_row(
    db: AsyncSession, requirement_id: uuid.UUID, feasibility_id: uuid.UUID
) -> FeasibilityStudy | None:
    stmt = select(FeasibilityStudy).where(
        FeasibilityStudy.id == feasibility_id, FeasibilityStudy.requirement_id == requirement_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _get_strategy_row(
    db: AsyncSession, requirement_id: uuid.UUID, strategy_id: uuid.UUID
) -> TestStrategy | None:
    stmt = select(TestStrategy).where(
        TestStrategy.id == strategy_id, TestStrategy.requirement_id == requirement_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _latest_status_for_requirement(
    db: AsyncSession, model: type, requirement_id: uuid.UUID
) -> str:
    """Single-row "most recent status" lookup for FeasibilityStudy/TestStrategy,
    used by get_requirement_latest_statuses(). `model` must be one of those two
    ORM classes (both expose `.requirement_id`, `.status`, `.sequence`)."""
    stmt = (
        select(model.status)
        .where(model.requirement_id == requirement_id)
        .order_by(model.sequence.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    status_value = result.scalar_one_or_none()
    return status_value.value if status_value is not None else "none"


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


def _latest_status_subquery(model: type):
    """Shared shape for the "most recent status per requirement" subqueries
    used by list_requirements(): a window function ranking each model's rows
    by `.sequence` (not `.created_at` - see AIAnalysis.sequence's docstring
    for why) within each requirement_id, so joining on rn == 1 picks the
    latest row deterministically. `model` is one of AIAnalysis,
    FeasibilityStudy, TestStrategy (all share requirement_id/status/sequence)."""
    return select(
        model.requirement_id,
        model.status,
        func.row_number()
        .over(partition_by=model.requirement_id, order_by=model.sequence.desc())
        .label("rn"),
    ).subquery()


async def list_requirements(
    db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID
) -> list[tuple[Requirement, str, str, str]]:
    """Returns (requirement, latest_analysis_status, latest_feasibility_status,
    latest_strategy_status) tuples, newest requirement first. Each latest_*
    status is "none" if the requirement has never had one of that kind, else
    the status of its most recently created row of that kind."""
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.viewer)

    latest_analysis = _latest_status_subquery(AIAnalysis)
    latest_feasibility = _latest_status_subquery(FeasibilityStudy)
    latest_strategy = _latest_status_subquery(TestStrategy)

    stmt = (
        select(Requirement, latest_analysis.c.status, latest_feasibility.c.status, latest_strategy.c.status)
        .outerjoin(
            latest_analysis,
            (latest_analysis.c.requirement_id == Requirement.id) & (latest_analysis.c.rn == 1),
        )
        .outerjoin(
            latest_feasibility,
            (latest_feasibility.c.requirement_id == Requirement.id) & (latest_feasibility.c.rn == 1),
        )
        .outerjoin(
            latest_strategy,
            (latest_strategy.c.requirement_id == Requirement.id) & (latest_strategy.c.rn == 1),
        )
        .where(Requirement.project_id == project_id)
        .order_by(Requirement.created_at.desc())
    )
    result = await db.execute(stmt)
    return [
        (
            requirement,
            analysis_status.value if analysis_status is not None else "none",
            feasibility_status.value if feasibility_status is not None else "none",
            strategy_status.value if strategy_status is not None else "none",
        )
        for requirement, analysis_status, feasibility_status, strategy_status in result.all()
    ]


async def get_requirement(
    db: AsyncSession, project_id: uuid.UUID, requirement_id: uuid.UUID, user_id: uuid.UUID
) -> Requirement:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.viewer)
    requirement = await _get_requirement_row(db, project_id, requirement_id)
    if requirement is None:
        raise RequirementNotFoundError()
    return requirement


async def get_latest_feasibility_and_strategy_status(
    db: AsyncSession, requirement_id: uuid.UUID
) -> tuple[str, str]:
    """(latest_feasibility_status, latest_strategy_status) for one requirement.
    Does not itself check membership - callers already hold a
    membership-validated Requirement (from get_requirement/create_requirement/
    update_requirement) before calling this."""
    feasibility_status = await _latest_status_for_requirement(db, FeasibilityStudy, requirement_id)
    strategy_status = await _latest_status_for_requirement(db, TestStrategy, requirement_id)
    return feasibility_status, strategy_status


async def get_requirement_latest_statuses(
    db: AsyncSession, project_id: uuid.UUID, requirement_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[Requirement, str, str]:
    """Same lookup as get_requirement(), plus (latest_feasibility_status,
    latest_strategy_status) for the single-requirement detail response."""
    requirement = await get_requirement(db, project_id, requirement_id, user_id)
    feasibility_status, strategy_status = await get_latest_feasibility_and_strategy_status(
        db, requirement_id
    )
    return requirement, feasibility_status, strategy_status


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


# --- Feasibility Studies --------------------------------------------------


async def create_feasibility_study(
    db: AsyncSession,
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: dict,
) -> FeasibilityStudy:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.member)
    requirement = await _get_requirement_row(db, project_id, requirement_id)
    if requirement is None:
        raise RequirementNotFoundError()

    feasibility = FeasibilityStudy(
        requirement_id=requirement.id,
        status=FeasibilityStatus.draft,
        payload=payload,
        created_by=user_id,
    )
    db.add(feasibility)
    await db.commit()
    await db.refresh(feasibility)
    return feasibility


async def list_feasibility_studies(
    db: AsyncSession, project_id: uuid.UUID, requirement_id: uuid.UUID, user_id: uuid.UUID
) -> list[FeasibilityStudy]:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.viewer)
    requirement = await _get_requirement_row(db, project_id, requirement_id)
    if requirement is None:
        raise RequirementNotFoundError()

    stmt = (
        select(FeasibilityStudy)
        .where(FeasibilityStudy.requirement_id == requirement_id)
        .order_by(FeasibilityStudy.sequence.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_feasibility_study(
    db: AsyncSession,
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    feasibility_id: uuid.UUID,
    user_id: uuid.UUID,
) -> FeasibilityStudy:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.viewer)
    requirement = await _get_requirement_row(db, project_id, requirement_id)
    if requirement is None:
        raise RequirementNotFoundError()

    feasibility = await _get_feasibility_row(db, requirement_id, feasibility_id)
    if feasibility is None:
        raise FeasibilityNotFoundError()
    return feasibility


async def update_feasibility_payload(
    db: AsyncSession,
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    feasibility_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: dict,
) -> FeasibilityStudy:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.member)
    requirement = await _get_requirement_row(db, project_id, requirement_id)
    if requirement is None:
        raise RequirementNotFoundError()

    feasibility = await _get_feasibility_row(db, requirement_id, feasibility_id)
    if feasibility is None:
        raise FeasibilityNotFoundError()
    if feasibility.status != FeasibilityStatus.draft:
        raise FeasibilityNotDraftError()

    feasibility.payload = payload
    await db.commit()
    await db.refresh(feasibility)
    return feasibility


async def approve_feasibility_study(
    db: AsyncSession,
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    feasibility_id: uuid.UUID,
    user_id: uuid.UUID,
) -> FeasibilityStudy:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.member)
    requirement = await _get_requirement_row(db, project_id, requirement_id)
    if requirement is None:
        raise RequirementNotFoundError()

    feasibility = await _get_feasibility_row(db, requirement_id, feasibility_id)
    if feasibility is None:
        raise FeasibilityNotFoundError()
    if feasibility.status != FeasibilityStatus.draft:
        raise FeasibilityNotDraftError()

    feasibility.status = FeasibilityStatus.approved
    feasibility.approved_by = user_id
    feasibility.approved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(feasibility)
    return feasibility


async def reject_feasibility_study(
    db: AsyncSession,
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    feasibility_id: uuid.UUID,
    user_id: uuid.UUID,
) -> FeasibilityStudy:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.member)
    requirement = await _get_requirement_row(db, project_id, requirement_id)
    if requirement is None:
        raise RequirementNotFoundError()

    feasibility = await _get_feasibility_row(db, requirement_id, feasibility_id)
    if feasibility is None:
        raise FeasibilityNotFoundError()
    if feasibility.status != FeasibilityStatus.draft:
        raise FeasibilityNotDraftError()

    feasibility.status = FeasibilityStatus.rejected
    await db.commit()
    await db.refresh(feasibility)
    return feasibility


# --- Test Strategies -------------------------------------------------------


async def create_test_strategy(
    db: AsyncSession,
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: dict,
) -> TestStrategy:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.member)
    requirement = await _get_requirement_row(db, project_id, requirement_id)
    if requirement is None:
        raise RequirementNotFoundError()

    strategy = TestStrategy(
        requirement_id=requirement.id,
        status=StrategyStatus.draft,
        payload=payload,
        created_by=user_id,
    )
    db.add(strategy)
    await db.commit()
    await db.refresh(strategy)
    return strategy


async def list_test_strategies(
    db: AsyncSession, project_id: uuid.UUID, requirement_id: uuid.UUID, user_id: uuid.UUID
) -> list[TestStrategy]:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.viewer)
    requirement = await _get_requirement_row(db, project_id, requirement_id)
    if requirement is None:
        raise RequirementNotFoundError()

    stmt = (
        select(TestStrategy)
        .where(TestStrategy.requirement_id == requirement_id)
        .order_by(TestStrategy.sequence.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_test_strategy(
    db: AsyncSession,
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    strategy_id: uuid.UUID,
    user_id: uuid.UUID,
) -> TestStrategy:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.viewer)
    requirement = await _get_requirement_row(db, project_id, requirement_id)
    if requirement is None:
        raise RequirementNotFoundError()

    strategy = await _get_strategy_row(db, requirement_id, strategy_id)
    if strategy is None:
        raise StrategyNotFoundError()
    return strategy


async def update_test_strategy_payload(
    db: AsyncSession,
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    strategy_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: dict,
) -> TestStrategy:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.member)
    requirement = await _get_requirement_row(db, project_id, requirement_id)
    if requirement is None:
        raise RequirementNotFoundError()

    strategy = await _get_strategy_row(db, requirement_id, strategy_id)
    if strategy is None:
        raise StrategyNotFoundError()
    if strategy.status != StrategyStatus.draft:
        raise StrategyNotDraftError()

    strategy.payload = payload
    await db.commit()
    await db.refresh(strategy)
    return strategy


async def approve_test_strategy(
    db: AsyncSession,
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    strategy_id: uuid.UUID,
    user_id: uuid.UUID,
) -> TestStrategy:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.member)
    requirement = await _get_requirement_row(db, project_id, requirement_id)
    if requirement is None:
        raise RequirementNotFoundError()

    strategy = await _get_strategy_row(db, requirement_id, strategy_id)
    if strategy is None:
        raise StrategyNotFoundError()
    if strategy.status != StrategyStatus.draft:
        raise StrategyNotDraftError()

    strategy.status = StrategyStatus.approved
    strategy.approved_by = user_id
    strategy.approved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(strategy)
    return strategy


async def reject_test_strategy(
    db: AsyncSession,
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    strategy_id: uuid.UUID,
    user_id: uuid.UUID,
) -> TestStrategy:
    await project_repository.require_membership(db, project_id, user_id, ProjectRole.member)
    requirement = await _get_requirement_row(db, project_id, requirement_id)
    if requirement is None:
        raise RequirementNotFoundError()

    strategy = await _get_strategy_row(db, requirement_id, strategy_id)
    if strategy is None:
        raise StrategyNotFoundError()
    if strategy.status != StrategyStatus.draft:
        raise StrategyNotDraftError()

    strategy.status = StrategyStatus.rejected
    await db.commit()
    await db.refresh(strategy)
    return strategy


async def get_approved_feasibility_payload(
    db: AsyncSession, requirement_id: uuid.UUID
) -> dict | None:
    """Returns the payload of the most recently *approved* FeasibilityStudy
    for this requirement, or None if none has been approved. Used by
    service.generate_test_strategy() to pass feasibility context into the
    AI provider when available - no error is raised if none exists, since
    generating a test strategy never requires an approved feasibility study.
    Does not itself check membership; callers already hold a validated
    requirement (fetched via a membership-checked function) before calling."""
    stmt = (
        select(FeasibilityStudy.payload)
        .where(
            FeasibilityStudy.requirement_id == requirement_id,
            FeasibilityStudy.status == FeasibilityStatus.approved,
        )
        .order_by(FeasibilityStudy.sequence.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
