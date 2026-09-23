"""Tests for /api/v1/projects/{project_id}/test-cases/{test_case_id}/
automation-script/* (automation domain): generate (create vs regenerate),
get/patch/approve lifecycle, version history, role enforcement, project
isolation, and that the mock AI provider's generated script is a genuinely
runnable Playwright file referencing the given environment's base_url.
"""
from collections.abc import Awaitable, Callable

from httpx import AsyncClient


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
        "preconditions": "A registered user account exists.",
        "test_data": "Valid email/password pair.",
        "steps": ["Navigate to the login page.", "Enter valid credentials.", "Submit."],
        "expected_result": "The user is logged in and redirected to the dashboard.",
        "automation_candidate": True,
    }
    resp = await client.post(f"/api/v1/projects/{project_id}/test-cases", json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_environment(client: AsyncClient, headers: dict, project_id: str, base_url: str) -> dict:
    resp = await client.post(
        f"/api/v1/projects/{project_id}/environments",
        json={"name": "Staging", "base_url": base_url},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _script_base(project_id: str, test_case_id: str) -> str:
    return f"/api/v1/projects/{project_id}/test-cases/{test_case_id}/automation-script"


async def test_generate_creates_draft_script_first_time_then_regenerates(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    test_case = await _create_test_case(client, owner["headers"], project["id"], requirement["id"])
    environment = await _create_environment(
        client, owner["headers"], project["id"], "https://staging.example.com"
    )

    resp = await client.post(
        _script_base(project["id"], test_case["id"]),
        json={"environment_id": environment["id"]},
        headers=owner["headers"],
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["test_case_id"] == test_case["id"]
    assert body["status"] == "draft"
    assert body["current_version"]["version_number"] == 1
    assert body["current_version"]["source"] == "ai"
    code = body["current_version"]["code"]
    assert "@playwright/test" in code
    assert "staging.example.com" in code
    assert test_case["title"] in code
    for step in test_case["steps"]:
        assert step in code

    # Regenerating returns 200 (not 201) and bumps the version number.
    regen = await client.post(
        _script_base(project["id"], test_case["id"]),
        json={"environment_id": environment["id"]},
        headers=owner["headers"],
    )
    assert regen.status_code == 200, regen.text
    assert regen.json()["current_version"]["version_number"] == 2


async def test_generate_without_environment_uses_placeholder(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    test_case = await _create_test_case(client, owner["headers"], project["id"], requirement["id"])

    resp = await client.post(
        _script_base(project["id"], test_case["id"]), json={}, headers=owner["headers"]
    )
    assert resp.status_code == 201, resp.text
    assert "@playwright/test" in resp.json()["current_version"]["code"]


async def test_get_returns_404_before_generation(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    test_case = await _create_test_case(client, owner["headers"], project["id"], requirement["id"])

    resp = await client.get(_script_base(project["id"], test_case["id"]), headers=owner["headers"])
    assert resp.status_code == 404


async def test_patch_creates_human_version_and_resets_to_draft(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    test_case = await _create_test_case(client, owner["headers"], project["id"], requirement["id"])
    await client.post(_script_base(project["id"], test_case["id"]), json={}, headers=owner["headers"])

    approve_resp = await client.post(
        f"{_script_base(project['id'], test_case['id'])}/approve", headers=owner["headers"]
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "approved"

    new_code = "import { test, expect } from '@playwright/test';\ntest('x', async () => {});\n"
    patch_resp = await client.patch(
        _script_base(project["id"], test_case["id"]),
        json={"code": new_code},
        headers=owner["headers"],
    )
    assert patch_resp.status_code == 200, patch_resp.text
    body = patch_resp.json()
    assert body["status"] == "draft"  # any edit resets approval
    assert body["current_version"]["version_number"] == 2
    assert body["current_version"]["source"] == "human"
    assert body["current_version"]["code"] == new_code


async def test_approve_lifecycle(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    test_case = await _create_test_case(client, owner["headers"], project["id"], requirement["id"])
    await client.post(_script_base(project["id"], test_case["id"]), json={}, headers=owner["headers"])

    approve_resp = await client.post(
        f"{_script_base(project['id'], test_case['id'])}/approve", headers=owner["headers"]
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "approved"

    approve_again = await client.post(
        f"{_script_base(project['id'], test_case['id'])}/approve", headers=owner["headers"]
    )
    assert approve_again.status_code == 409


async def test_versions_list_omits_code_newest_first(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    test_case = await _create_test_case(client, owner["headers"], project["id"], requirement["id"])
    await client.post(_script_base(project["id"], test_case["id"]), json={}, headers=owner["headers"])
    await client.patch(
        _script_base(project["id"], test_case["id"]),
        json={"code": "import { test } from '@playwright/test';\n"},
        headers=owner["headers"],
    )

    versions_resp = await client.get(
        f"{_script_base(project['id'], test_case['id'])}/versions", headers=owner["headers"]
    )
    assert versions_resp.status_code == 200
    versions = versions_resp.json()
    assert len(versions) == 2
    assert versions[0]["version_number"] == 2
    assert versions[0]["source"] == "human"
    assert versions[1]["version_number"] == 1
    assert versions[1]["source"] == "ai"
    for v in versions:
        assert "code" not in v


async def test_role_enforcement(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    test_case = await _create_test_case(client, owner["headers"], project["id"], requirement["id"])
    viewer = await register_user()
    await _add_member(client, owner["headers"], project["id"], viewer["email"], "viewer")
    stranger = await register_user()

    generate_viewer = await client.post(
        _script_base(project["id"], test_case["id"]), json={}, headers=viewer["headers"]
    )
    assert generate_viewer.status_code == 403

    generate_stranger = await client.post(
        _script_base(project["id"], test_case["id"]), json={}, headers=stranger["headers"]
    )
    assert generate_stranger.status_code == 404

    await client.post(_script_base(project["id"], test_case["id"]), json={}, headers=owner["headers"])

    patch_viewer = await client.patch(
        _script_base(project["id"], test_case["id"]), json={"code": "x"}, headers=viewer["headers"]
    )
    assert patch_viewer.status_code == 403

    approve_viewer = await client.post(
        f"{_script_base(project['id'], test_case['id'])}/approve", headers=viewer["headers"]
    )
    assert approve_viewer.status_code == 403


async def test_project_isolation(
    user_a: dict, user_b: dict, client: AsyncClient
) -> None:
    project_b = await _create_project(client, user_b["headers"], "B's project")
    requirement_b = await _create_requirement(client, user_b["headers"], project_b["id"])
    test_case_b = await _create_test_case(client, user_b["headers"], project_b["id"], requirement_b["id"])
    await client.post(
        _script_base(project_b["id"], test_case_b["id"]), json={}, headers=user_b["headers"]
    )
    base = _script_base(project_b["id"], test_case_b["id"])

    assert (await client.get(base, headers=user_a["headers"])).status_code == 404
    assert (await client.post(base, json={}, headers=user_a["headers"])).status_code == 404
    assert (
        await client.patch(base, json={"code": "x"}, headers=user_a["headers"])
    ).status_code == 404
    assert (await client.post(f"{base}/approve", headers=user_a["headers"])).status_code == 404
    assert (await client.get(f"{base}/versions", headers=user_a["headers"])).status_code == 404
