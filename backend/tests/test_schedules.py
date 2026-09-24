"""Tests for /api/v1/projects/{project_id}/schedules/* (schedules domain,
Sprint 7) and the Celery Beat periodic task that fires due jobs.

Most tests here use the standard shared `client`/`db_session` fixture (one
connection wrapped in an outer transaction + SAVEPOINTs, rolled back after
the test - see tests/conftest.py) and cover the API contract: creation
(including next_run_at computation and validation 400s), list/get/patch/
delete, role enforcement, and project isolation.

The two periodic-task tests (`test_periodic_tick_fires_due_schedule_...` /
`test_periodic_tick_skips_unautomatable_job_...`) deliberately do NOT use
that shared fixture, for the exact same reason `test_executions.py`'s own
real-engine E2E tests don't: `run_due_scheduled_jobs_sync()` (like
`run_automated_execution_sync()`) opens its own dedicated DB engine/
connection, which - being a genuinely separate Postgres connection - cannot
see rows created through the shared fixture's single connection/SAVEPOINT-
wrapped, never-truly-committed transaction. So these two tests use their own
independent engine/sessions with real commits instead, the same pattern
`test_executions.py`'s `test_automated_execution_against_reachable_url_passes`
etc. already established.
"""
import uuid as uuid_lib
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.domains.automation import repository as automation_repository
from app.domains.automation import service as automation_service
from app.domains.environments import repository as environments_repository
from app.domains.executions.models import Execution, ExecutionKind
from app.domains.identity.models import User
from app.domains.projects.models import Project, ProjectMember, ProjectRole
from app.domains.requirements.models import Requirement, RequirementPriority
from app.domains.schedules import repository as schedules_repository
from app.domains.schedules import tasks as schedules_tasks
from app.domains.schedules.models import ScheduledJob
from app.domains.testcases.models import ExecutionType, TestCaseCategory, TestCaseSeverity
from app.domains.testcases.models import TestCase as TestCaseModel  # avoid pytest collecting this as a test class
from app.domains.testcases.models import TestCaseSource, TestCaseStatus, TestingLevel

# Import the existing E2E fixture/helpers from test_executions.py rather than
# duplicating a second local HTTP server - pytest discovers a fixture
# imported into a test module's namespace the same as one defined there.
from tests.test_executions import local_http_server  # noqa: F401


async def _create_project(client: AsyncClient, headers: dict, name: str = "Project X") -> dict:
    resp = await client.post("/api/v1/projects", json={"name": name}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _add_member(client: AsyncClient, owner_headers: dict, project_id: str, email: str, role: str) -> None:
    resp = await client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"email": email, "role": role},
        headers=owner_headers,
    )
    assert resp.status_code == 201, resp.text


async def _create_requirement(client: AsyncClient, headers: dict, project_id: str) -> dict:
    body = {"title": "Users can log in", "description": "As a user, I want to log in with email/password."}
    resp = await client.post(f"/api/v1/projects/{project_id}/requirements", json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_test_case(client: AsyncClient, headers: dict, project_id: str, requirement_id: str) -> dict:
    body = {
        "requirement_id": requirement_id,
        "title": "Login succeeds with valid credentials",
        "category": "positive",
        "testing_level": "ui",
        "priority": "high",
        "severity": "major",
        "steps": ["Navigate to the login page.", "Submit valid credentials."],
        "expected_result": "The user is logged in.",
        "automation_candidate": True,
    }
    resp = await client.post(f"/api/v1/projects/{project_id}/test-cases", json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_environment(client: AsyncClient, headers: dict, project_id: str, base_url: str = "https://staging.example.com") -> dict:
    resp = await client.post(
        f"/api/v1/projects/{project_id}/environments",
        json={"name": "Staging", "base_url": base_url},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _generate_and_approve_script_via_api(client: AsyncClient, headers: dict, project_id: str, test_case_id: str) -> None:
    resp = await client.post(
        f"/api/v1/projects/{project_id}/test-cases/{test_case_id}/automation-script",
        json={},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    approve = await client.post(
        f"/api/v1/projects/{project_id}/test-cases/{test_case_id}/automation-script/approve",
        headers=headers,
    )
    assert approve.status_code == 200, approve.text


def _base(project_id: str) -> str:
    return f"/api/v1/projects/{project_id}/schedules"


# --- Pure cron computation -----------------------------------------------


def test_compute_next_run_at_exact_value_for_known_cron_and_now() -> None:
    base_time = datetime(2026, 1, 1, 10, 5, 0, tzinfo=timezone.utc)
    next_run = schedules_repository.compute_next_run_at("0 2 * * *", base_time)
    assert next_run == datetime(2026, 1, 2, 2, 0, 0, tzinfo=timezone.utc)


def test_validate_cron_expression_rejects_garbage() -> None:
    try:
        schedules_repository.validate_cron_expression("not a cron expression")
        assert False, "expected InvalidCronExpressionError"
    except schedules_repository.InvalidCronExpressionError:
        pass


# --- API: create ------------------------------------------------------------


async def test_create_schedule_computes_next_run_at(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    test_case = await _create_test_case(client, owner["headers"], project["id"], requirement["id"])
    environment = await _create_environment(client, owner["headers"], project["id"])
    await _generate_and_approve_script_via_api(client, owner["headers"], project["id"], test_case["id"])

    before = datetime.now(timezone.utc)
    resp = await client.post(
        _base(project["id"]),
        json={
            "name": "Nightly smoke test",
            "test_case_id": test_case["id"],
            "environment_id": environment["id"],
            "cron_expression": "0 2 * * *",
        },
        headers=owner["headers"],
    )
    after = datetime.now(timezone.utc)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "Nightly smoke test"
    assert body["cron_expression"] == "0 2 * * *"
    assert body["enabled"] is True
    assert body["last_run_at"] is None
    assert body["created_by"] == owner["user"]["id"]
    assert body["test_case_id"] == test_case["id"]
    assert body["environment_id"] == environment["id"]
    assert body["project_id"] == project["id"]

    # next_run_at must equal what compute_next_run_at() derives from "now"
    # bracketed by [before, after] around the request - since the cron is
    # daily at 02:00 UTC, that value is identical for any "now" in that
    # (sub-second) window unless the window straddles 02:00 UTC itself.
    expected = schedules_repository.compute_next_run_at("0 2 * * *", before)
    expected_after = schedules_repository.compute_next_run_at("0 2 * * *", after)
    assert expected == expected_after, "test flaked across the 02:00 UTC boundary - rerun"
    assert datetime.fromisoformat(body["next_run_at"]) == expected


async def test_create_schedule_disabled_has_no_next_run_at(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    test_case = await _create_test_case(client, owner["headers"], project["id"], requirement["id"])
    environment = await _create_environment(client, owner["headers"], project["id"])
    await _generate_and_approve_script_via_api(client, owner["headers"], project["id"], test_case["id"])

    resp = await client.post(
        _base(project["id"]),
        json={
            "name": "Disabled job",
            "test_case_id": test_case["id"],
            "environment_id": environment["id"],
            "cron_expression": "0 2 * * *",
            "enabled": False,
        },
        headers=owner["headers"],
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["enabled"] is False
    assert resp.json()["next_run_at"] is None


async def test_create_schedule_rejects_invalid_cron_expression(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    test_case = await _create_test_case(client, owner["headers"], project["id"], requirement["id"])
    environment = await _create_environment(client, owner["headers"], project["id"])

    resp = await client.post(
        _base(project["id"]),
        json={
            "name": "Bad cron",
            "test_case_id": test_case["id"],
            "environment_id": environment["id"],
            "cron_expression": "not a cron expression",
        },
        headers=owner["headers"],
    )
    assert resp.status_code == 400, resp.text


async def test_create_schedule_without_approved_script_returns_400(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    test_case = await _create_test_case(client, owner["headers"], project["id"], requirement["id"])
    environment = await _create_environment(client, owner["headers"], project["id"])

    resp = await client.post(
        _base(project["id"]),
        json={
            "name": "No script yet",
            "test_case_id": test_case["id"],
            "environment_id": environment["id"],
            "cron_expression": "0 2 * * *",
        },
        headers=owner["headers"],
    )
    assert resp.status_code == 400, resp.text

    # Still 400 with a draft (never-approved) script.
    await client.post(
        f"/api/v1/projects/{project['id']}/test-cases/{test_case['id']}/automation-script",
        json={},
        headers=owner["headers"],
    )
    resp2 = await client.post(
        _base(project["id"]),
        json={
            "name": "Still no approved script",
            "test_case_id": test_case["id"],
            "environment_id": environment["id"],
            "cron_expression": "0 2 * * *",
        },
        headers=owner["headers"],
    )
    assert resp2.status_code == 400, resp2.text


# --- API: list/get/patch/delete --------------------------------------------


async def test_list_get_patch_delete_schedule(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    test_case = await _create_test_case(client, owner["headers"], project["id"], requirement["id"])
    env1 = await _create_environment(client, owner["headers"], project["id"], base_url="https://one.example.com")
    env2 = await _create_environment(client, owner["headers"], project["id"], base_url="https://two.example.com")
    await _generate_and_approve_script_via_api(client, owner["headers"], project["id"], test_case["id"])

    create1 = await client.post(
        _base(project["id"]),
        json={"name": "First", "test_case_id": test_case["id"], "environment_id": env1["id"], "cron_expression": "0 2 * * *"},
        headers=owner["headers"],
    )
    assert create1.status_code == 201, create1.text
    job1 = create1.json()

    create2 = await client.post(
        _base(project["id"]),
        json={"name": "Second", "test_case_id": test_case["id"], "environment_id": env1["id"], "cron_expression": "0 3 * * *"},
        headers=owner["headers"],
    )
    assert create2.status_code == 201, create2.text
    job2 = create2.json()

    # list: newest first (sequence desc)
    list_resp = await client.get(_base(project["id"]), headers=owner["headers"])
    assert list_resp.status_code == 200
    assert [j["id"] for j in list_resp.json()] == [job2["id"], job1["id"]]

    # get
    get_resp = await client.get(f"{_base(project['id'])}/{job1['id']}", headers=owner["headers"])
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == job1["id"]

    get_missing = await client.get(f"{_base(project['id'])}/{uuid_lib.uuid4()}", headers=owner["headers"])
    assert get_missing.status_code == 404

    # patch: disable -> next_run_at becomes null
    disable_resp = await client.patch(
        f"{_base(project['id'])}/{job1['id']}", json={"enabled": False}, headers=owner["headers"]
    )
    assert disable_resp.status_code == 200, disable_resp.text
    assert disable_resp.json()["enabled"] is False
    assert disable_resp.json()["next_run_at"] is None

    # patch: re-enable -> next_run_at recomputed (non-null)
    enable_resp = await client.patch(
        f"{_base(project['id'])}/{job1['id']}", json={"enabled": True}, headers=owner["headers"]
    )
    assert enable_resp.status_code == 200, enable_resp.text
    assert enable_resp.json()["enabled"] is True
    assert enable_resp.json()["next_run_at"] is not None

    # patch: change cron_expression -> next_run_at recomputed from new cron
    before = datetime.now(timezone.utc)
    cron_resp = await client.patch(
        f"{_base(project['id'])}/{job1['id']}", json={"cron_expression": "30 4 * * *"}, headers=owner["headers"]
    )
    after = datetime.now(timezone.utc)
    assert cron_resp.status_code == 200, cron_resp.text
    assert cron_resp.json()["cron_expression"] == "30 4 * * *"
    expected = schedules_repository.compute_next_run_at("30 4 * * *", before)
    expected_after = schedules_repository.compute_next_run_at("30 4 * * *", after)
    assert expected == expected_after, "test flaked across the 04:30 UTC boundary - rerun"
    assert datetime.fromisoformat(cron_resp.json()["next_run_at"]) == expected

    # patch: change environment_id
    env_resp = await client.patch(
        f"{_base(project['id'])}/{job1['id']}", json={"environment_id": env2["id"]}, headers=owner["headers"]
    )
    assert env_resp.status_code == 200, env_resp.text
    assert env_resp.json()["environment_id"] == env2["id"]

    # patch: invalid cron -> 400
    bad_cron_resp = await client.patch(
        f"{_base(project['id'])}/{job1['id']}", json={"cron_expression": "garbage"}, headers=owner["headers"]
    )
    assert bad_cron_resp.status_code == 400

    # patch: unknown environment -> 404
    bad_env_resp = await client.patch(
        f"{_base(project['id'])}/{job1['id']}", json={"environment_id": str(uuid_lib.uuid4())}, headers=owner["headers"]
    )
    assert bad_env_resp.status_code == 404

    # delete
    delete_resp = await client.delete(f"{_base(project['id'])}/{job1['id']}", headers=owner["headers"])
    assert delete_resp.status_code == 204
    assert (await client.get(f"{_base(project['id'])}/{job1['id']}", headers=owner["headers"])).status_code == 404


# --- Role enforcement / project isolation -----------------------------------


async def test_role_enforcement(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    test_case = await _create_test_case(client, owner["headers"], project["id"], requirement["id"])
    environment = await _create_environment(client, owner["headers"], project["id"])
    await _generate_and_approve_script_via_api(client, owner["headers"], project["id"], test_case["id"])

    viewer = await register_user()
    await _add_member(client, owner["headers"], project["id"], viewer["email"], "viewer")
    member = await register_user()
    await _add_member(client, owner["headers"], project["id"], member["email"], "member")
    stranger = await register_user()

    # viewer cannot create
    create_viewer = await client.post(
        _base(project["id"]),
        json={"name": "X", "test_case_id": test_case["id"], "environment_id": environment["id"], "cron_expression": "0 2 * * *"},
        headers=viewer["headers"],
    )
    assert create_viewer.status_code == 403

    # viewer can read
    assert (await client.get(_base(project["id"]), headers=viewer["headers"])).status_code == 200

    # member can create
    create_member = await client.post(
        _base(project["id"]),
        json={"name": "Y", "test_case_id": test_case["id"], "environment_id": environment["id"], "cron_expression": "0 2 * * *"},
        headers=member["headers"],
    )
    assert create_member.status_code == 201, create_member.text
    job = create_member.json()

    # member cannot delete (admin-only)
    assert (await client.delete(f"{_base(project['id'])}/{job['id']}", headers=member["headers"])).status_code == 403

    # owner (admin) can delete
    assert (await client.delete(f"{_base(project['id'])}/{job['id']}", headers=owner["headers"])).status_code == 204

    # stranger (non-member) -> 404, never 403
    assert (await client.get(_base(project["id"]), headers=stranger["headers"])).status_code == 404


async def test_project_isolation(user_a: dict, user_b: dict, client: AsyncClient) -> None:
    project_b = await _create_project(client, user_b["headers"], "B's project")
    requirement_b = await _create_requirement(client, user_b["headers"], project_b["id"])
    test_case_b = await _create_test_case(client, user_b["headers"], project_b["id"], requirement_b["id"])
    environment_b = await _create_environment(client, user_b["headers"], project_b["id"])
    await _generate_and_approve_script_via_api(client, user_b["headers"], project_b["id"], test_case_b["id"])

    create_resp = await client.post(
        _base(project_b["id"]),
        json={"name": "B job", "test_case_id": test_case_b["id"], "environment_id": environment_b["id"], "cron_expression": "0 2 * * *"},
        headers=user_b["headers"],
    )
    assert create_resp.status_code == 201, create_resp.text
    job = create_resp.json()
    base_b = _base(project_b["id"])

    assert (await client.get(base_b, headers=user_a["headers"])).status_code == 404
    assert (await client.get(f"{base_b}/{job['id']}", headers=user_a["headers"])).status_code == 404
    assert (
        await client.patch(f"{base_b}/{job['id']}", json={"enabled": False}, headers=user_a["headers"])
    ).status_code == 404
    assert (await client.delete(f"{base_b}/{job['id']}", headers=user_a["headers"])).status_code == 404
    assert (
        await client.post(
            base_b,
            json={"name": "X", "test_case_id": test_case_b["id"], "environment_id": environment_b["id"], "cron_expression": "0 2 * * *"},
            headers=user_a["headers"],
        )
    ).status_code == 404


# --- Real periodic-task engine proof ----------------------------------------
#
# See this module's docstring for why these two tests use their own
# independent engine/sessions (real commits) rather than the shared
# `client`/`db_session` fixture.


async def _setup_project_with_test_case(engine) -> dict:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        user = User(
            email=f"sched-e2e-{uuid_lib.uuid4().hex[:10]}@example.com",
            full_name="Schedules E2E Test User",
            hashed_password="not-a-real-hash",
        )
        session.add(user)
        await session.flush()

        project = Project(name="Schedules E2E Project")
        session.add(project)
        await session.flush()

        session.add(ProjectMember(project_id=project.id, user_id=user.id, role=ProjectRole.admin))

        requirement = Requirement(
            project_id=project.id,
            title="Schedules E2E requirement",
            description="Used to test the periodic scheduling task end-to-end.",
            priority=RequirementPriority.medium,
            created_by=user.id,
        )
        session.add(requirement)
        await session.flush()

        test_case = TestCaseModel(
            project_id=project.id,
            requirement_id=requirement.id,
            code="TC-001",
            title="Homepage loads",
            category=TestCaseCategory.positive,
            testing_level=TestingLevel.ui,
            priority=RequirementPriority.medium,
            severity=TestCaseSeverity.major,
            preconditions="",
            test_data="",
            steps=["Load the homepage."],
            expected_result="The homepage is visible.",
            business_rule="",
            automation_candidate=True,
            execution_type=ExecutionType.automation,
            status=TestCaseStatus.approved,
            source=TestCaseSource.human,
            tags=[],
            created_by=user.id,
        )
        session.add(test_case)
        await session.commit()

        return {"user_id": user.id, "project_id": project.id, "test_case_id": test_case.id}


async def _generate_and_approve_script(engine, ids: dict) -> None:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        await automation_service.generate_script(
            session, ids["project_id"], ids["test_case_id"], ids["user_id"], environment_id=None
        )
    async with AsyncSession(engine, expire_on_commit=False) as session:
        await automation_repository.approve_script(
            session, ids["project_id"], ids["test_case_id"], ids["user_id"]
        )


async def _unapprove_script(engine, ids: dict) -> None:
    """Human edit -> resets status back to "draft" (same invariant every
    other edit/regeneration path in the automation domain uses)."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        await automation_repository.update_script(
            session, ids["project_id"], ids["test_case_id"], ids["user_id"], code="// edited, needs re-approval"
        )


async def _create_environment_row(engine, ids: dict, base_url: str) -> uuid_lib.UUID:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        environment = await environments_repository.create_environment(
            session,
            ids["project_id"],
            ids["user_id"],
            name="e2e-env",
            base_url=base_url,
            variables=None,
        )
        return environment.id


async def _create_due_schedule_row(engine, ids: dict, environment_id, cron_expression: str = "0 2 * * *") -> uuid_lib.UUID:
    """Inserts a ScheduledJob directly (bypassing the API/repository's
    "next occurrence is always in the future" computation) with
    `next_run_at` already in the past, so the periodic task's `get_due_
    schedules()` query picks it up immediately."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        job = ScheduledJob(
            project_id=ids["project_id"],
            test_case_id=ids["test_case_id"],
            environment_id=environment_id,
            name="Due job",
            cron_expression=cron_expression,
            enabled=True,
            next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            created_by=ids["user_id"],
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job.id


async def test_periodic_tick_fires_due_schedule_and_updates_run_timestamps(
    local_http_server: str,
) -> None:
    import os

    database_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url, future=True)
    try:
        ids = await _setup_project_with_test_case(engine)
        await _generate_and_approve_script(engine, ids)
        environment_id = await _create_environment_row(engine, ids, local_http_server)
        schedule_id = await _create_due_schedule_row(engine, ids, environment_id)

        before_tick = datetime.now(timezone.utc)
        schedules_tasks.run_due_scheduled_jobs_sync()
        after_tick = datetime.now(timezone.utc)

        async with AsyncSession(engine, expire_on_commit=False) as session:
            result = await session.execute(select(ScheduledJob).where(ScheduledJob.id == schedule_id))
            job = result.scalar_one()

            exec_result = await session.execute(
                select(Execution).where(
                    Execution.project_id == ids["project_id"],
                    Execution.test_case_id == ids["test_case_id"],
                    Execution.type == ExecutionKind.automated,
                )
            )
            executions = list(exec_result.scalars().all())

        assert len(executions) == 1
        assert executions[0].triggered_by == ids["user_id"]

        assert job.last_run_at is not None
        assert before_tick <= job.last_run_at <= after_tick
        assert job.next_run_at is not None
        # Recomputed relative to "now at tick time" - must be a fresh future
        # occurrence, strictly after last_run_at, not the stale pre-tick value.
        assert job.next_run_at > job.last_run_at
        assert job.enabled is True
    finally:
        async with AsyncSession(engine, expire_on_commit=False) as cleanup:
            proj = await cleanup.get(Project, ids["project_id"])
            if proj is not None:
                await cleanup.delete(proj)
            usr = await cleanup.get(User, ids["user_id"])
            if usr is not None:
                await cleanup.delete(usr)
            await cleanup.commit()
        await engine.dispose()


async def test_periodic_tick_skips_unautomatable_job_without_disabling() -> None:
    import os

    database_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url, future=True)
    try:
        ids = await _setup_project_with_test_case(engine)
        await _generate_and_approve_script(engine, ids)
        environment_id = await _create_environment_row(engine, ids, "https://staging.example.com")
        schedule_id = await _create_due_schedule_row(engine, ids, environment_id)

        # The script becomes un-approved (a human edit) after the schedule
        # was created but before this tick runs.
        await _unapprove_script(engine, ids)

        schedules_tasks.run_due_scheduled_jobs_sync()

        async with AsyncSession(engine, expire_on_commit=False) as session:
            result = await session.execute(select(ScheduledJob).where(ScheduledJob.id == schedule_id))
            job = result.scalar_one()

            exec_result = await session.execute(
                select(Execution).where(
                    Execution.project_id == ids["project_id"],
                    Execution.test_case_id == ids["test_case_id"],
                )
            )
            executions = list(exec_result.scalars().all())

        assert executions == []
        assert job.enabled is True  # not disabled
        assert job.last_run_at is None  # tick did not fire
        # next_run_at is left untouched (still in the past) so the very next
        # tick re-checks it immediately, per the task's skip-silently contract.
        assert job.next_run_at is not None and job.next_run_at < datetime.now(timezone.utc)
    finally:
        async with AsyncSession(engine, expire_on_commit=False) as cleanup:
            proj = await cleanup.get(Project, ids["project_id"])
            if proj is not None:
                await cleanup.delete(proj)
            usr = await cleanup.get(User, ids["user_id"])
            if usr is not None:
                await cleanup.delete(usr)
            await cleanup.commit()
        await engine.dispose()
