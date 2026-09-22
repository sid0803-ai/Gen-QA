"""Business logic that crosses into the ai domain (generating a new
AIAnalysis via AIService). Pure project-scoped persistence/authorization
stays in repository.py, same convention as app.domains.projects.service.
"""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.ai.schemas import RequirementInput
from app.domains.ai.service import AIService
from app.domains.requirements import repository
from app.domains.requirements.models import AIAnalysis

_ai_service = AIService()


async def generate_analysis(
    db: AsyncSession, project_id: uuid.UUID, requirement_id: uuid.UUID, user_id: uuid.UUID
) -> AIAnalysis:
    """Fetch the requirement (viewer-level membership check), run it through
    AIService to get a validated payload, then persist it as a new draft
    AIAnalysis row (repository.create_analysis re-checks membership at the
    'member' level required to actually trigger an analysis)."""
    requirement = await repository.get_requirement(db, project_id, requirement_id, user_id)

    ai_input = RequirementInput(
        title=requirement.title,
        description=requirement.description,
        business_objective=requirement.business_objective,
        acceptance_criteria=requirement.acceptance_criteria,
        priority=requirement.priority.value,
    )
    payload = _ai_service.analyze_requirement(ai_input)

    return await repository.create_analysis(
        db, project_id, requirement_id, user_id, payload.model_dump(mode="json")
    )
