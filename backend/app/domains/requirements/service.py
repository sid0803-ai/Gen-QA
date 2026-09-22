"""Business logic that crosses into the ai domain (generating a new
AIAnalysis/FeasibilityStudy/TestStrategy via AIService). Pure project-scoped
persistence/authorization stays in repository.py, same convention as
app.domains.projects.service.
"""
import uuid
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.ai.schemas import FeasibilityStudyPayload, RequirementInput, TestDesignPayload, TestStrategyPayload
from app.domains.ai.service import AIService
from app.domains.requirements import repository
from app.domains.requirements.models import AIAnalysis, FeasibilityStudy, TestDesign, TestDesignStatus, TestStrategy
from app.domains.testcases import service as testcases_service
from app.domains.testcases.models import TestCase

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


async def generate_test_design(
    db: AsyncSession,
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    user_id: uuid.UUID,
    scope: Literal["api", "ui", "both"],
) -> TestDesign:
    """Same shape as generate_test_strategy(): if an approved TestStrategy
    exists for this requirement, its payload is passed to the AI provider as
    extra context (its applicable testing levels influence which levels the
    generated scenarios use); if none exists, None is passed and generation
    proceeds anyway (a test design never requires one)."""
    requirement = await repository.get_requirement(db, project_id, requirement_id, user_id)

    ai_input = _build_ai_input(requirement)
    approved_strategy_payload = await repository.get_approved_strategy_payload(db, requirement_id)
    strategy = (
        TestStrategyPayload.model_validate(approved_strategy_payload)
        if approved_strategy_payload is not None
        else None
    )
    payload = _ai_service.generate_test_design(ai_input, strategy, scope)

    return await repository.create_test_design(
        db, project_id, requirement_id, user_id, payload.model_dump(mode="json")
    )


async def approve_test_design(
    db: AsyncSession,
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    test_design_id: uuid.UUID,
    user_id: uuid.UUID,
) -> tuple[TestDesign, list[TestCase]]:
    """Approve a draft TestDesign and, in the SAME transaction, promote
    every scenario with `include == True` into a permanent TestCase row
    (source="ai", status="approved", test_design_id set - see
    app.domains.testcases.service.promote_scenario_to_test_case()).
    Approval and promotion are committed together here (one db.commit() at
    the end) so they're atomic: either both happen, or neither does."""
    test_design = await repository.get_draft_test_design_for_approval(
        db, project_id, requirement_id, test_design_id, user_id
    )

    payload = TestDesignPayload.model_validate(test_design.payload)
    created_test_cases: list[TestCase] = []
    for scenario in payload.scenarios:
        if not scenario.include:
            continue
        test_case = await testcases_service.promote_scenario_to_test_case(
            db,
            project_id=project_id,
            requirement_id=requirement_id,
            test_design_id=test_design.id,
            created_by=user_id,
            title=scenario.title,
            category=scenario.category,
            testing_level=scenario.testing_level,
            priority=scenario.priority,
            severity=scenario.severity,
            preconditions=scenario.preconditions,
            test_data=scenario.test_data,
            steps=scenario.steps,
            expected_result=scenario.expected_result,
            business_rule=scenario.business_rule,
            automation_candidate=scenario.automation_candidate,
        )
        created_test_cases.append(test_case)

    test_design.status = TestDesignStatus.approved
    test_design.approved_by = user_id
    test_design.approved_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(test_design)
    for test_case in created_test_cases:
        await db.refresh(test_case)
    return test_design, created_test_cases
