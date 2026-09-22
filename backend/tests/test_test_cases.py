"""Tests for /api/v1/projects/{project_id}/test-cases/* (testcases domain):
manual CRUD, role enforcement (viewer 403, non-member 404, delete requires
admin), filtering by each query param, search, version history creation on
PATCH, concurrent-code-generation safety, and project isolation.

Unlike test_test_design.py (which nests under a requirement), the Test Case
Repository is project-scoped, so most helpers here only need a project +
requirement pair to attach test cases to.
"""
import asyncio
import os
import uuid as uuid_lib
from collections.abc import Awaitable, Callable

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.domains.identity.models import User
from app.domains.projects.models import Project, ProjectMember, ProjectRole
from app.domains.requirements.models import Requirement, RequirementPriority
from app.domains.testcases import repository as testcases_repository

DETAIL_KEYS = {
    "id",
    "project_id",
    "requirement_id",
    "test_design_id",
    "code",
    "title",
    "category",
    "testing_level",
    "priority",
    "severity",
    "preconditions",
    "test_data",
    "steps",
    "expected_result",
    "business_rule",
    "automation_candidate",
    "execution_type",
    "status",
    "source",
    "tags",
    "created_by",
    "created_at",
    "updated_by",
    "updated_at",
}
LIST_ITEM_KEYS = {
    "id",
    "code",
    "title",
    "testing_level",
    "category",
    "priority",
    "severity",
    "status",
    "source",
    "automation_candidate",
    "execution_type",
    "requirement_id",
    "requirement_title",
    "tags",
    "created_at",
}


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


async def _create_requirement(
    client: AsyncClient,
    headers: dict,
    project_id: str,
    title: str = "Users can log in",
    description: str = "As a user, I want to log in with my email and password.",
    **extra,
) -> dict:
    body = {"title": title, "description": description, **extra}
    resp = await client.post(
        f"/api/v1/projects/{project_id}/requirements", json=body, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _base(project_id: str) -> str:
    return f"/api/v1/projects/{project_id}/test-cases"


def _payload(requirement_id: str, **overrides) -> dict:
    body = {
        "requirement_id": requirement_id,
        "title": "Login succeeds with valid credentials",
        "category": "positive",
        "testing_level": "functional",
        "priority": "high",
        "severity": "major",
        "preconditions": "A registered user account exists.",
        "test_data": "Valid email/password pair.",
        "steps": ["Navigate to the login page.", "Enter valid credentials.", "Submit."],
        "expected_result": "The user is logged in and redirected to the dashboard.",
        "business_rule": "Only registered users may log in.",
        "automation_candidate": True,
        "tags": ["smoke"],
    }
    body.update(overrides)
    return body


async def _create_test_case(client: AsyncClient, headers: dict, project_id: str, **overrides) -> dict:
    resp = await client.post(_base(project_id), json=_payload(**overrides), headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_create_test_case_manual_full_shape(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])

    resp = await client.post(
        _base(project["id"]), json=_payload(requirement["id"]), headers=owner["headers"]
    )
    assert resp.status_code == 201, resp.text
    test_case = resp.json()

    assert set(test_case.keys()) == DETAIL_KEYS
    assert test_case["code"] == "TC-001"
    assert test_case["source"] == "human"
    assert test_case["status"] == "draft"
    assert test_case["test_design_id"] is None
    assert test_case["requirement_id"] == requirement["id"]
    assert test_case["project_id"] == project["id"]
    assert test_case["created_by"] == owner["user"]["id"]
    assert test_case["updated_by"] is None
    # automation_candidate=True -> execution_type defaults to "automation".
    assert test_case["execution_type"] == "automation"


async def test_execution_type_defaults_from_automation_candidate(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])

    automatable = await _create_test_case(
        client, owner["headers"], project["id"], requirement_id=requirement["id"], automation_candidate=True
    )
    assert automatable["execution_type"] == "automation"

    manual = await _create_test_case(
        client, owner["headers"], project["id"], requirement_id=requirement["id"], automation_candidate=False
    )
    assert manual["execution_type"] == "manual"

    explicit = await _create_test_case(
        client,
        owner["headers"],
        project["id"],
        requirement_id=requirement["id"],
        automation_candidate=True,
        execution_type="hybrid",
    )
    assert explicit["execution_type"] == "hybrid"


async def test_sequential_code_generation_within_a_project(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])

    codes = []
    for _ in range(3):
        tc = await _create_test_case(client, owner["headers"], project["id"], requirement_id=requirement["id"])
        codes.append(tc["code"])
    assert codes == ["TC-001", "TC-002", "TC-003"]


async def test_code_counter_is_scoped_per_project(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project_a = await _create_project(client, owner["headers"], "Project A")
    project_b = await _create_project(client, owner["headers"], "Project B")
    requirement_a = await _create_requirement(client, owner["headers"], project_a["id"])
    requirement_b = await _create_requirement(client, owner["headers"], project_b["id"])

    tc_a = await _create_test_case(client, owner["headers"], project_a["id"], requirement_id=requirement_a["id"])
    tc_b = await _create_test_case(client, owner["headers"], project_b["id"], requirement_id=requirement_b["id"])
    assert tc_a["code"] == "TC-001"
    assert tc_b["code"] == "TC-001"


async def test_role_enforcement(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    viewer = await register_user()
    await _add_member(client, owner["headers"], project["id"], viewer["email"], "viewer")
    member = await register_user()
    await _add_member(client, owner["headers"], project["id"], member["email"], "member")
    stranger = await register_user()

    # viewer: read-only.
    create_resp = await client.post(
        _base(project["id"]), json=_payload(requirement["id"]), headers=viewer["headers"]
    )
    assert create_resp.status_code == 403

    # non-member: 404 everywhere, never a leak.
    list_resp = await client.get(_base(project["id"]), headers=stranger["headers"])
    assert list_resp.status_code == 404
    create_stranger_resp = await client.post(
        _base(project["id"]), json=_payload(requirement["id"]), headers=stranger["headers"]
    )
    assert create_stranger_resp.status_code == 404

    test_case = await _create_test_case(client, owner["headers"], project["id"], requirement_id=requirement["id"])

    patch_viewer = await client.patch(
        f"{_base(project['id'])}/{test_case['id']}", json={"title": "New title"}, headers=viewer["headers"]
    )
    assert patch_viewer.status_code == 403

    approve_viewer = await client.post(
        f"{_base(project['id'])}/{test_case['id']}/approve", headers=viewer["headers"]
    )
    assert approve_viewer.status_code == 403

    # delete requires admin - member is not enough.
    delete_member = await client.delete(f"{_base(project['id'])}/{test_case['id']}", headers=member["headers"])
    assert delete_member.status_code == 403

    # admin can delete.
    delete_admin = await client.delete(f"{_base(project['id'])}/{test_case['id']}", headers=owner["headers"])
    assert delete_admin.status_code == 204

    get_after_delete = await client.get(f"{_base(project['id'])}/{test_case['id']}", headers=owner["headers"])
    assert get_after_delete.status_code == 404


async def test_get_test_case_detail_full_fields(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    created = await _create_test_case(client, owner["headers"], project["id"], requirement_id=requirement["id"])

    resp = await client.get(f"{_base(project['id'])}/{created['id']}", headers=owner["headers"])
    assert resp.status_code == 200
    detail = resp.json()
    assert set(detail.keys()) == DETAIL_KEYS
    assert detail["steps"] == _payload(requirement["id"])["steps"]


async def test_list_shape_and_join_with_requirement_title(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"], title="Distinctive Title")
    await _create_test_case(client, owner["headers"], project["id"], requirement_id=requirement["id"])

    resp = await client.get(_base(project["id"]), headers=owner["headers"])
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert set(items[0].keys()) == LIST_ITEM_KEYS
    assert items[0]["requirement_title"] == "Distinctive Title"


async def test_list_filtering_by_each_query_param(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    req1 = await _create_requirement(client, owner["headers"], project["id"], title="Req One")
    req2 = await _create_requirement(client, owner["headers"], project["id"], title="Req Two")

    tc1 = await _create_test_case(
        client,
        owner["headers"],
        project["id"],
        requirement_id=req1["id"],
        title="Login happy path",
        category="positive",
        testing_level="functional",
        priority="high",
        automation_candidate=True,
    )
    tc2 = await _create_test_case(
        client,
        owner["headers"],
        project["id"],
        requirement_id=req2["id"],
        title="Payment API rejects invalid card",
        category="negative",
        testing_level="api",
        priority="critical",
        automation_candidate=False,
    )
    # Approve tc2 so status filtering has something to distinguish.
    await client.post(f"{_base(project['id'])}/{tc2['id']}/approve", headers=owner["headers"])

    async def _ids(**params) -> set[str]:
        resp = await client.get(_base(project["id"]), params=params, headers=owner["headers"])
        assert resp.status_code == 200, resp.text
        return {item["id"] for item in resp.json()}

    assert await _ids(requirement_id=req1["id"]) == {tc1["id"]}
    assert await _ids(requirement_id=req2["id"]) == {tc2["id"]}
    assert await _ids(testing_level="api") == {tc2["id"]}
    assert await _ids(category="negative") == {tc2["id"]}
    assert await _ids(priority="critical") == {tc2["id"]}
    assert await _ids(status="draft") == {tc1["id"]}
    assert await _ids(status="approved") == {tc2["id"]}
    assert await _ids(automation_candidate=True) == {tc1["id"]}
    assert await _ids(automation_candidate=False) == {tc2["id"]}
    assert await _ids(search="Payment") == {tc2["id"]}
    assert await _ids(search="login") == {tc1["id"]}  # case-insensitive substring
    assert await _ids() == {tc1["id"], tc2["id"]}


async def test_patch_creates_version_and_increments_version_number(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    test_case = await _create_test_case(client, owner["headers"], project["id"], requirement_id=requirement["id"])

    # No versions before any edit.
    versions_resp = await client.get(
        f"{_base(project['id'])}/{test_case['id']}/versions", headers=owner["headers"]
    )
    assert versions_resp.status_code == 200
    assert versions_resp.json() == []

    patch1 = await client.patch(
        f"{_base(project['id'])}/{test_case['id']}",
        json={"title": "First edit", "priority": "critical"},
        headers=owner["headers"],
    )
    assert patch1.status_code == 200
    assert patch1.json()["title"] == "First edit"
    assert patch1.json()["priority"] == "critical"
    assert patch1.json()["updated_by"] == owner["user"]["id"]

    patch2 = await client.patch(
        f"{_base(project['id'])}/{test_case['id']}",
        json={"title": "Second edit", "automation_candidate": False},
        headers=owner["headers"],
    )
    assert patch2.status_code == 200
    assert patch2.json()["title"] == "Second edit"

    versions_resp = await client.get(
        f"{_base(project['id'])}/{test_case['id']}/versions", headers=owner["headers"]
    )
    assert versions_resp.status_code == 200
    versions = versions_resp.json()
    assert len(versions) == 2
    # Newest first.
    assert versions[0]["version_number"] == 2
    assert versions[1]["version_number"] == 1
    assert versions[0]["snapshot"]["title"] == "Second edit"
    assert versions[0]["snapshot"]["automation_candidate"] is False
    # Priority set in edit 1 persists into edit 2's snapshot (edit 2 didn't
    # touch it).
    assert versions[0]["snapshot"]["priority"] == "critical"
    assert versions[1]["snapshot"]["title"] == "First edit"
    assert versions[1]["snapshot"]["priority"] == "critical"
    for version in versions:
        assert version["edited_by"] == owner["user"]["id"]
        assert version["test_case_id"] == test_case["id"]


async def test_approve_test_case_lifecycle(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    test_case = await _create_test_case(client, owner["headers"], project["id"], requirement_id=requirement["id"])
    assert test_case["status"] == "draft"

    approve_resp = await client.post(f"{_base(project['id'])}/{test_case['id']}/approve", headers=owner["headers"])
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "approved"

    approve_again = await client.post(f"{_base(project['id'])}/{test_case['id']}/approve", headers=owner["headers"])
    assert approve_again.status_code == 409


async def test_project_isolation_test_case_unreachable_from_other_project(
    user_a: dict, user_b: dict, client: AsyncClient
) -> None:
    project_b = await _create_project(client, user_b["headers"], "B's project")
    requirement_b = await _create_requirement(client, user_b["headers"], project_b["id"])
    test_case = await _create_test_case(
        client, user_b["headers"], project_b["id"], requirement_id=requirement_b["id"]
    )
    base_b = _base(project_b["id"])

    assert (await client.get(base_b, headers=user_a["headers"])).status_code == 404
    assert (await client.get(f"{base_b}/{test_case['id']}", headers=user_a["headers"])).status_code == 404
    assert (
        await client.post(base_b, json=_payload(requirement_b["id"]), headers=user_a["headers"])
    ).status_code == 404
    assert (
        await client.patch(f"{base_b}/{test_case['id']}", json={"title": "hijacked"}, headers=user_a["headers"])
    ).status_code == 404
    assert (
        await client.post(f"{base_b}/{test_case['id']}/approve", headers=user_a["headers"])
    ).status_code == 404
    assert (await client.delete(f"{base_b}/{test_case['id']}", headers=user_a["headers"])).status_code == 404
    assert (
        await client.get(f"{base_b}/{test_case['id']}/versions", headers=user_a["headers"])
    ).status_code == 404


async def test_concurrent_test_case_creation_produces_unique_sequential_codes() -> None:
    """Directly exercises testcases.repository.create_test_case()'s
    concurrency-safe code generation (see `_next_code()`'s docstring) by
    firing several concurrent creations at the SAME project from
    independent DB connections/transactions - the same class of race a
    naive `count(*) + 1` implementation would fail under.

    Deliberately bypasses the shared single-connection `client`/`db_session`
    test fixtures used by every other test in this file: those fixtures
    hand every request in a test the SAME AsyncSession/connection (wrapped
    in one outer transaction + SAVEPOINTs), so concurrent requests through
    them would not actually exercise cross-transaction row locking the way
    genuinely concurrent requests against the real running API would - they
    would either serialize on that one connection or trip SQLAlchemy's
    "session already in use" guard. This test instead opens its own
    independent AsyncSession (and therefore its own DB transaction) per
    concurrent creation, matching how two real concurrent HTTP requests
    would each get their own request-scoped session in production.
    """
    database_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url, future=True)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as setup_session:
            user = User(
                email=f"concurrency-{uuid_lib.uuid4().hex[:10]}@example.com",
                full_name="Concurrency Test User",
                hashed_password="not-a-real-hash",
            )
            setup_session.add(user)
            await setup_session.flush()

            project = Project(name="Concurrency Project")
            setup_session.add(project)
            await setup_session.flush()

            setup_session.add(
                ProjectMember(project_id=project.id, user_id=user.id, role=ProjectRole.admin)
            )

            requirement = Requirement(
                project_id=project.id,
                title="Concurrency requirement",
                description="Used to test concurrent test-case code generation.",
                priority=RequirementPriority.medium,
                created_by=user.id,
            )
            setup_session.add(requirement)
            await setup_session.commit()

            project_id = project.id
            requirement_id = requirement.id
            user_id = user.id

        concurrency = 8

        async def _create_one() -> str:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                test_case = await testcases_repository.create_test_case(
                    session,
                    project_id,
                    user_id,
                    requirement_id=requirement_id,
                    title="Concurrent test case",
                    category="positive",
                    testing_level="functional",
                    priority="medium",
                    severity="major",
                    preconditions="",
                    test_data="",
                    steps=[],
                    expected_result="",
                    business_rule="",
                    automation_candidate=False,
                    execution_type=None,
                    tags=None,
                )
                return test_case.code

        codes = await asyncio.gather(*[_create_one() for _ in range(concurrency)])

        assert len(codes) == concurrency
        # No duplicates: the exact bug a naive count(*) + 1 implementation
        # would produce under concurrency.
        assert len(set(codes)) == concurrency, f"duplicate codes generated under concurrency: {codes}"
        # No gaps either: the counter is strictly sequential regardless of
        # completion order.
        assert sorted(codes) == [f"TC-{i:03d}" for i in range(1, concurrency + 1)]

        async with AsyncSession(engine, expire_on_commit=False) as cleanup_session:
            proj = await cleanup_session.get(Project, project_id)
            if proj is not None:
                await cleanup_session.delete(proj)
            usr = await cleanup_session.get(User, user_id)
            if usr is not None:
                await cleanup_session.delete(usr)
            await cleanup_session.commit()
    finally:
        await engine.dispose()
