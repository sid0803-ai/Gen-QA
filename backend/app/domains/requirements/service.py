"""Business logic that crosses into the ai domain (generating a new
AIAnalysis/FeasibilityStudy/TestStrategy via AIService). Pure project-scoped
persistence/authorization stays in repository.py, same convention as
app.domains.projects.service.
"""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.ai.schemas import FeasibilityStudyPayload, RequirementInput
from app.domains.ai.service import AIService
from app.domains.requirements import repository
from app.domains.requirements.models import AIAnalysis, FeasibilityStudy, TestStrategy

_ai_service = AIService()


def _build_ai_input(requirement) -> RequirementInput:
    return RequirementInput(
        title=requirement.title,
        description=requirement.description,
        business_objective=requirement.business_objective,
        acceptance_criteria=requirement.acceptance_criteria,
        priority=requirement.priority.value,
    )


async def generate_analysis(
    db: AsyncSession, project_id: uuid.UUID, requirement_id: uuid.UUID, user_id: uuid.UUID
) -> AIAnalysis:
    """Fetch the requirement (viewer-level membership check), run it through
    AIService to get a validated payload, then persist it as a new draft
    AIAnalysis row (repository.create_analysis re-checks membership at the
    'member' level required to actually trigger an analysis)."""
    requirement = await repository.get_requirement(db, project_id, requirement_id, user_id)

    ai_input = _build_ai_input(requirement)
    payload = _ai_service.analyze_requirement(ai_input)

    return await repository.create_analysis(
        db, project_id, requirement_id, user_id, payload.model_dump(mode="json")
    )


async def generate_feasibility_study(
    db: AsyncSession, project_id: uuid.UUID, requirement_id: uuid.UUID, user_id: uuid.UUID
) -> FeasibilityStudy:
    """Same shape as generate_analysis(), for a FeasibilityStudy."""
    requirement = await repository.get_requirement(db, project_id, requirement_id, user_id)

    ai_input = _build_ai_input(requirement)
    payload = _ai_service.feasibility_study(ai_input)

    return await repository.create_feasibility_study(
        db, project_id, requirement_id, user_id, payload.model_dump(mode="json")
    )


async def generate_test_strategy(
    db: AsyncSession, project_id: uuid.UUID, requirement_id: uuid.UUID, user_id: uuid.UUID
) -> TestStrategy:
    """Same shape as generate_analysis(), for a TestStrategy. If an approved
    FeasibilityStudy exists for this requirement, its payload is passed to
    the AI provider as extra context; if none exists, None is passed and
    generation proceeds anyway (a test strategy never requires one)."""
    requirement = await repository.get_requirement(db, project_id, requirement_id, user_id)

    ai_input = _build_ai_input(requirement)
    approved_feasibility_payload = await repository.get_approved_feasibility_payload(
        db, requirement_id
    )
    feasibility = (
        FeasibilityStudyPayload.model_validate(approved_feasibility_payload)
        if approved_feasibility_payload is not None
        else None
    )
    payload = _ai_service.generate_test_strategy(ai_input, feasibility)

    return await repository.create_test_strategy(
        db, project_id, requirement_id, user_id, payload.model_dump(mode="json")
    )
