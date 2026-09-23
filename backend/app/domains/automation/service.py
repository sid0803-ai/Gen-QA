"""Business logic that crosses into the ai/environments domains (generating
a new AutomationScript version via AIService). Pure project/test-case-scoped
persistence/authorization stays in repository.py, same convention as
app.domains.requirements.service.
"""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.ai.schemas import EnvironmentInput, TestCaseInput
from app.domains.ai.service import AIService
from app.domains.automation import repository
from app.domains.automation.models import AutomationScript, ScriptVersion
from app.domains.environments import repository as environments_repository

_ai_service = AIService()


async def generate_script(
    db: AsyncSession,
    project_id: uuid.UUID,
    test_case_id: uuid.UUID,
    user_id: uuid.UUID,
    environment_id: uuid.UUID | None,
) -> tuple[AutomationScript, list[ScriptVersion], bool]:
    """Fetch the test case (and, if given, the environment - both membership-
    checked), run them through AIService to get a runnable Playwright script,
    then persist it as a new ScriptVersion (creating the AutomationScript row
    on first use). Returns (script, versions, created) - see
    repository.save_generated_script()."""
    test_case = await repository.get_test_case_for_generation(db, project_id, test_case_id, user_id)

    environment = None
    if environment_id is not None:
        # Re-checks membership (harmless, already verified above) and raises
        # environments_repository.EnvironmentNotFoundError if the given
        # environment doesn't exist in this project.
        environment = await environments_repository.get_environment(
            db, project_id, environment_id, user_id
        )

    test_case_input = TestCaseInput(
        title=test_case.title,
        preconditions=test_case.preconditions,
        steps=list(test_case.steps or []),
        expected_result=test_case.expected_result,
    )
    environment_input = EnvironmentInput(base_url=environment.base_url) if environment else None

    code = _ai_service.generate_playwright_script(test_case_input, environment_input)

    return await repository.save_generated_script(
        db, test_case_id=test_case_id, user_id=user_id, code=code
    )
