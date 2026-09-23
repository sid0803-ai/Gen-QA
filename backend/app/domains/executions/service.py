"""Business logic that crosses into Celery (enqueuing the automated-run
task). Pure project-scoped persistence/authorization stays in repository.py,
same convention as every other domain's service.py.
"""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.executions import repository
from app.domains.executions.models import Execution, ExecutionStatus


async def create_manual_execution(
    db: AsyncSession,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    test_case_id: uuid.UUID,
    environment_id: uuid.UUID,
    result_status: ExecutionStatus,
    actual_result: str | None,
    comments: str | None,
) -> Execution:
    return await repository.create_manual_execution(
        db,
        project_id,
        user_id,
        test_case_id=test_case_id,
        environment_id=environment_id,
        result_status=result_status,
        actual_result=actual_result,
        comments=comments,
    )


async def create_automated_execution(
    db: AsyncSession,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    test_case_id: uuid.UUID,
    environment_id: uuid.UUID,
) -> Execution:
    """Creates the pending Execution row (committed - see
    repository.create_pending_automated_execution()'s own docstring on why
    the commit must happen before enqueueing), then hands it to Celery.
    Imported lazily so importing this module never requires a reachable
    broker - `run_automated_execution.delay(...)` only needs the broker at
    call time, not at import time, but keeping the import local here also
    keeps this module usable in contexts that never touch Celery at all."""
    execution = await repository.create_pending_automated_execution(
        db, project_id, user_id, test_case_id=test_case_id, environment_id=environment_id
    )

    from app.worker import run_automated_execution

    run_automated_execution.delay(str(execution.id))
    return execution
