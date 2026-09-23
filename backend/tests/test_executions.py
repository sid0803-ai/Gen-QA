"""Tests for /api/v1/projects/{project_id}/executions/* (executions domain).

Most tests here use the standard shared `client`/`db_session` fixture (one
connection wrapped in an outer transaction + SAVEPOINTs, rolled back after
the test - see tests/conftest.py) and cover the API contract: manual
immediate-completion, automated pending-on-create + validation/409 shapes,
list filtering, role enforcement, and project isolation.

The two tests that prove an automated execution's pass/fail signal is
genuinely derived from actually running the generated Playwright script
(`test_automated_execution_against_reachable_url_passes` /
`..._against_unreachable_url_fails`) deliberately do NOT use that shared
fixture. Celery's `task_always_eager` mode (set globally in conftest.py)
still runs the real `run_automated_execution` task inline, and that task
(see app.domains.executions.tasks._run()) opens its OWN dedicated DB engine/
connection to look up the execution/script/environment - which, being a
genuinely separate Postgres connection, cannot see rows created through the
shared fixture's single connection/SAVEPOINT-wrapped, never-truly-committed
transaction. So these two tests use their own independent engine/sessions
with real commits instead, the same pattern
`test_test_cases.py::test_concurrent_test_case_creation_produces_unique_sequential_codes`
already established for exactly this class of problem.
"""
import functools
import http.server
import os
import tempfile
import threading
import uuid as uuid_lib
from collections.abc import Awaitable, Callable

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.domains.automation import repository as automation_repository
from app.domains.automation import service as automation_service
from app.domains.environments import repository as environments_repository
from app.domains.executions import repository as executions_repository
from app.domains.executions import service as executions_service
from app.domains.executions.models import ExecutionStatus
from app.domains.identity.models import User
from app.domains.projects.models import Project, ProjectMember, ProjectRole
from app.domains.requirements.models import Requirement, RequirementPriority
from app.domains.testcases.models import ExecutionType, TestCaseCategory, TestCaseSeverity
from app.domains.testcases.models import TestCase as TestCaseModel  # avoid pytest collecting this as a test class
from app.domains.testcases.models import TestCaseSource, TestCaseStatus, TestingLevel


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


def _base(project_id: str) -> str:
    return f"/api/v1/projects/{project_id}/executions"


async def test_manual_execution_immediately_completed(
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
            "test_case_id": test_case["id"],
            "environment_id": environment["id"],
            "type": "manual",
            "status": "passed",
            "actual_result": "Logged in successfully.",
            "comments": "Looks good.",
        },
        headers=owner["headers"],
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["type"] == "manual"
    assert body["status"] == "passed"
    assert body["actual_result"] == "Logged in successfully."
    assert body["comments"] == "Looks good."
    assert body["completed_at"] is not None
    assert body["started_at"] is not None
    assert body["triggered_by"] == owner["user"]["id"]
    assert body["logs"] is None
    assert body["error_message"] is None


async def test_manual_execution_requires_terminal_status(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    test_case = await _create_test_case(client, owner["headers"], project["id"], requirement["id"])
    environment = await _create_environment(client, owner["headers"], project["id"])

    missing_status = await client.post(
        _base(project["id"]),
        json={"test_case_id": test_case["id"], "environment_id": environment["id"], "type": "manual"},
        headers=owner["headers"],
    )
    assert missing_status.status_code == 422

    bad_status = await client.post(
        _base(project["id"]),
        json={
            "test_case_id": test_case["id"],
            "environment_id": environment["id"],
            "type": "manual",
            "status": "pending",
        },
        headers=owner["headers"],
    )
    assert bad_status.status_code == 422


async def test_automated_execution_without_approved_script_returns_409(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    test_case = await _create_test_case(client, owner["headers"], project["id"], requirement["id"])
    environment = await _create_environment(client, owner["headers"], project["id"])

    resp = await client.post(
        _base(project["id"]),
        json={"test_case_id": test_case["id"], "environment_id": environment["id"], "type": "automated"},
        headers=owner["headers"],
    )
    assert resp.status_code == 409, resp.text

    # Still 409 with a draft (never-approved) script.
    await client.post(
        f"/api/v1/projects/{project['id']}/test-cases/{test_case['id']}/automation-script",
        json={},
        headers=owner["headers"],
    )
    resp2 = await client.post(
        _base(project["id"]),
        json={"test_case_id": test_case["id"], "environment_id": environment["id"], "type": "automated"},
        headers=owner["headers"],
    )
    assert resp2.status_code == 409, resp2.text


async def test_automated_execution_shape_rejects_manual_only_fields(
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
            "test_case_id": test_case["id"],
            "environment_id": environment["id"],
            "type": "automated",
            "status": "passed",
        },
        headers=owner["headers"],
    )
    assert resp.status_code == 422


async def test_list_filtering_and_ordering(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    tc1 = await _create_test_case(client, owner["headers"], project["id"], requirement["id"])
    tc2 = await _create_test_case(client, owner["headers"], project["id"], requirement["id"])
    env = await _create_environment(client, owner["headers"], project["id"])

    async def _manual(test_case_id: str, result_status: str) -> dict:
        resp = await client.post(
            _base(project["id"]),
            json={
                "test_case_id": test_case_id,
                "environment_id": env["id"],
                "type": "manual",
                "status": result_status,
            },
            headers=owner["headers"],
        )
        assert resp.status_code == 201, resp.text
        return resp.json()

    e1 = await _manual(tc1["id"], "passed")
    e2 = await _manual(tc2["id"], "failed")

    list_resp = await client.get(_base(project["id"]), headers=owner["headers"])
    assert list_resp.status_code == 200
    ids_newest_first = [e["id"] for e in list_resp.json()]
    assert ids_newest_first == [e2["id"], e1["id"]]

    by_test_case = await client.get(
        _base(project["id"]), params={"test_case_id": tc1["id"]}, headers=owner["headers"]
    )
    assert {e["id"] for e in by_test_case.json()} == {e1["id"]}

    by_status = await client.get(
        _base(project["id"]), params={"status": "failed"}, headers=owner["headers"]
    )
    assert {e["id"] for e in by_status.json()} == {e2["id"]}

    by_type = await client.get(
        _base(project["id"]), params={"type": "manual"}, headers=owner["headers"]
    )
    assert {e["id"] for e in by_type.json()} == {e1["id"], e2["id"]}

    get_resp = await client.get(f"{_base(project['id'])}/{e1['id']}", headers=owner["headers"])
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == e1["id"]


async def test_role_enforcement(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    test_case = await _create_test_case(client, owner["headers"], project["id"], requirement["id"])
    environment = await _create_environment(client, owner["headers"], project["id"])
    viewer = await register_user()
    await _add_member(client, owner["headers"], project["id"], viewer["email"], "viewer")
    stranger = await register_user()

    create_viewer = await client.post(
        _base(project["id"]),
        json={
            "test_case_id": test_case["id"],
            "environment_id": environment["id"],
            "type": "manual",
            "status": "passed",
        },
        headers=viewer["headers"],
    )
    assert create_viewer.status_code == 403

    list_stranger = await client.get(_base(project["id"]), headers=stranger["headers"])
    assert list_stranger.status_code == 404


async def test_project_isolation(user_a: dict, user_b: dict, client: AsyncClient) -> None:
    project_b = await _create_project(client, user_b["headers"], "B's project")
    requirement_b = await _create_requirement(client, user_b["headers"], project_b["id"])
    test_case_b = await _create_test_case(client, user_b["headers"], project_b["id"], requirement_b["id"])
    environment_b = await _create_environment(client, user_b["headers"], project_b["id"])
    create_resp = await client.post(
        _base(project_b["id"]),
        json={
            "test_case_id": test_case_b["id"],
            "environment_id": environment_b["id"],
            "type": "manual",
            "status": "passed",
        },
        headers=user_b["headers"],
    )
    execution = create_resp.json()
    base_b = _base(project_b["id"])

    assert (await client.get(base_b, headers=user_a["headers"])).status_code == 404
    assert (
        await client.get(f"{base_b}/{execution['id']}", headers=user_a["headers"])
    ).status_code == 404
    assert (
        await client.post(
            base_b,
            json={
                "test_case_id": test_case_b["id"],
                "environment_id": environment_b["id"],
                "type": "manual",
                "status": "passed",
            },
            headers=user_a["headers"],
        )
    ).status_code == 404


# --- Real end-to-end execution engine proof ---------------------------------
#
# See this module's docstring for why these two tests use their own
# independent engine/sessions (real commits) rather than the shared
# `client`/`db_session` fixture.


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A002 - matches base signature
        pass


@pytest.fixture
def local_http_server():
    """A trivial local HTTP server (Python's http.server) on a random free
    port, serving a temp directory - the 'reachable environment' target for
    the real-execution test below."""
    tmp_dir = tempfile.mkdtemp()
    handler = functools.partial(_QuietHandler, directory=tmp_dir)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


async def _setup_project_with_test_case(engine) -> dict:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        user = User(
            email=f"exec-e2e-{uuid_lib.uuid4().hex[:10]}@example.com",
            full_name="Execution E2E Test User",
            hashed_password="not-a-real-hash",
        )
        session.add(user)
        await session.flush()

        project = Project(name="Execution E2E Project")
        session.add(project)
        await session.flush()

        session.add(ProjectMember(project_id=project.id, user_id=user.id, role=ProjectRole.admin))

        requirement = Requirement(
            project_id=project.id,
            title="Execution E2E requirement",
            description="Used to test the real execution engine end-to-end.",
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


async def test_automated_execution_against_reachable_url_passes(
    local_http_server: str,
) -> None:
    database_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url, future=True)
    try:
        ids = await _setup_project_with_test_case(engine)
        await _generate_and_approve_script(engine, ids)
        environment_id = await _create_environment_row(engine, ids, local_http_server)

        async with AsyncSession(engine, expire_on_commit=False) as session:
            execution = await executions_service.create_automated_execution(
                session,
                ids["project_id"],
                ids["user_id"],
                test_case_id=ids["test_case_id"],
                environment_id=environment_id,
            )

        # task_always_eager (set globally in conftest.py) means the task ran
        # to completion, synchronously, before create_automated_execution()
        # above even returned - fetch a fresh copy to see its final state.
        async with AsyncSession(engine, expire_on_commit=False) as session:
            final = await executions_repository.get_execution(
                session, ids["project_id"], execution.id, ids["user_id"]
            )

        assert final.status == ExecutionStatus.passed, final.logs
        assert final.duration_ms is not None and final.duration_ms >= 0
        assert final.error_message is None
        assert final.logs
        assert final.started_at is not None
        assert final.completed_at is not None
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


async def test_automated_execution_against_unreachable_url_fails_or_errors() -> None:
    database_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url, future=True)
    try:
        ids = await _setup_project_with_test_case(engine)
        await _generate_and_approve_script(engine, ids)
        # Port 1 is a browser-blocked ("unsafe") port - page.goto() throws a
        # real navigation error for it, deterministically, without relying
        # on a slow connection-refused/timeout race.
        environment_id = await _create_environment_row(engine, ids, "http://127.0.0.1:1")

        async with AsyncSession(engine, expire_on_commit=False) as session:
            execution = await executions_service.create_automated_execution(
                session,
                ids["project_id"],
                ids["user_id"],
                test_case_id=ids["test_case_id"],
                environment_id=environment_id,
            )

        async with AsyncSession(engine, expire_on_commit=False) as session:
            final = await executions_repository.get_execution(
                session, ids["project_id"], execution.id, ids["user_id"]
            )

        assert final.status in (ExecutionStatus.failed, ExecutionStatus.error), final.logs
        assert final.error_message
        assert final.completed_at is not None
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
