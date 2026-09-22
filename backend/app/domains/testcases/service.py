"""Thin service layer for the testcases domain.

Most testcases logic is pure project-scoped CRUD/search and lives directly
in repository.py (same convention as app.domains.projects: there's no AI
generation step to orchestrate here the way app.domains.requirements.service
orchestrates app.domains.ai). service.py exists for layout symmetry with
every other domain and to hold the one bit of cross-domain orchestration
this domain exposes to a caller outside itself: promoting an approved
TestDesign scenario into a TestCase. It's called by
`app.domains.requirements.service.approve_test_design()` once per
`include == true` scenario, inside that same call's DB transaction, so a
TestDesign's approval and the TestCase rows it produces commit together
(all-or-nothing).
"""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.testcases import repository
from app.domains.testcases.models import TestCase


async def promote_scenario_to_test_case(
    db: AsyncSession,
    *,
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    test_design_id: uuid.UUID,
    created_by: uuid.UUID,
    title: str,
    category: str,
    testing_level: str,
    priority: str,
    severity: str,
    preconditions: str,
    test_data: str,
    steps: list[str],
    expected_result: str,
    business_rule: str,
    automation_candidate: bool,
) -> TestCase:
    return await repository.create_ai_test_case_draft(
        db,
        project_id=project_id,
        requirement_id=requirement_id,
        test_design_id=test_design_id,
        created_by=created_by,
        title=title,
        category=category,
        testing_level=testing_level,
        priority=priority,
        severity=severity,
        preconditions=preconditions,
        test_data=test_data,
        steps=steps,
        expected_result=expected_result,
        business_rule=business_rule,
        automation_candidate=automation_candidate,
    )
