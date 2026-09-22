"""Tests for /api/v1/projects/{project_id}/requirements/* : CRUD, role
enforcement, and project isolation."""
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


async def _create_requirement(
    client: AsyncClient,
    headers: dict,
    project_id: str,
    title: str = "Users can reset their password",
    description: str = "As a user, I want to reset my password via email so that I can regain account access.",
    **extra,
) -> dict:
    body = {"title": title, "description": description, **extra}
    resp = await client.post(
        f"/api/v1/projects/{project_id}/requirements", json=body, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_create_requirement_defaults_and_shape(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])

    requirement = await _create_requirement(client, owner["headers"], project["id"])
    assert requirement["title"] == "Users can reset their password"
    assert requirement["priority"] == "medium"
    assert requirement["project_id"] == project["id"]
    assert requirement["created_by"] == owner["user"]["id"]
    assert requirement["business_objective"] is None
    assert requirement["acceptance_criteria"] is None
    assert "id" in requirement and "created_at" in requirement and "updated_at" in requirement


async def test_create_requirement_custom_priority(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])

    requirement = await _create_requirement(
        client, owner["headers"], project["id"], priority="critical", business_objective="Reduce support load."
    )
    assert requirement["priority"] == "critical"
    assert requirement["business_objective"] == "Reduce support load."


async def test_create_requirement_viewer_forbidden(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    viewer = await register_user()
    await _add_member(client, owner["headers"], project["id"], viewer["email"], "viewer")

    resp = await client.post(
        f"/api/v1/projects/{project['id']}/requirements",
        json={"title": "X", "description": "Y"},
        headers=viewer["headers"],
    )
    assert resp.status_code == 403


async def test_create_requirement_non_member_returns_404(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    stranger = await register_user()

    resp = await client.post(
        f"/api/v1/projects/{project['id']}/requirements",
        json={"title": "X", "description": "Y"},
        headers=stranger["headers"],
    )
    assert resp.status_code == 404


async def test_list_requirements_shape_and_latest_status_none(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    await _create_requirement(client, owner["headers"], project["id"], title="Req A")

    resp = await client.get(f"/api/v1/projects/{project['id']}/requirements", headers=owner["headers"])
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    item = items[0]
    assert set(item.keys()) == {"id", "title", "priority", "latest_analysis_status", "created_at"}
    assert item["title"] == "Req A"
    assert item["latest_analysis_status"] == "none"


async def test_list_requirements_viewer_can_read(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    await _create_requirement(client, owner["headers"], project["id"])
    viewer = await register_user()
    await _add_member(client, owner["headers"], project["id"], viewer["email"], "viewer")

    resp = await client.get(f"/api/v1/projects/{project['id']}/requirements", headers=viewer["headers"])
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_get_requirement_detail(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])

    resp = await client.get(
        f"/api/v1/projects/{project['id']}/requirements/{requirement['id']}", headers=owner["headers"]
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == requirement["id"]


async def test_get_requirement_nonexistent_returns_404(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])

    resp = await client.get(
        f"/api/v1/projects/{project['id']}/requirements/00000000-0000-0000-0000-000000000000",
        headers=owner["headers"],
    )
    assert resp.status_code == 404


async def test_update_requirement_requires_member(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    viewer = await register_user()
    await _add_member(client, owner["headers"], project["id"], viewer["email"], "viewer")

    forbidden = await client.patch(
        f"/api/v1/projects/{project['id']}/requirements/{requirement['id']}",
        json={"title": "Hijacked"},
        headers=viewer["headers"],
    )
    assert forbidden.status_code == 403

    ok = await client.patch(
        f"/api/v1/projects/{project['id']}/requirements/{requirement['id']}",
        json={"title": "Renamed", "priority": "high"},
        headers=owner["headers"],
    )
    assert ok.status_code == 200
    assert ok.json()["title"] == "Renamed"
    assert ok.json()["priority"] == "high"


async def test_update_requirement_partial_leaves_other_fields(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(
        client, owner["headers"], project["id"], acceptance_criteria="Given/When/Then"
    )

    resp = await client.patch(
        f"/api/v1/projects/{project['id']}/requirements/{requirement['id']}",
        json={"priority": "low"},
        headers=owner["headers"],
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["priority"] == "low"
    assert updated["title"] == requirement["title"]
    assert updated["acceptance_criteria"] == "Given/When/Then"


async def test_delete_requirement_requires_admin(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    member = await register_user()
    await _add_member(client, owner["headers"], project["id"], member["email"], "member")

    forbidden = await client.delete(
        f"/api/v1/projects/{project['id']}/requirements/{requirement['id']}", headers=member["headers"]
    )
    assert forbidden.status_code == 403

    ok = await client.delete(
        f"/api/v1/projects/{project['id']}/requirements/{requirement['id']}", headers=owner["headers"]
    )
    assert ok.status_code == 204

    gone = await client.get(
        f"/api/v1/projects/{project['id']}/requirements/{requirement['id']}", headers=owner["headers"]
    )
    assert gone.status_code == 404


async def test_project_isolation_requirement_unreachable_from_other_project(
    user_a: dict, user_b: dict, client: AsyncClient
) -> None:
    project_b = await _create_project(client, user_b["headers"], "B's project")
    requirement_b = await _create_requirement(client, user_b["headers"], project_b["id"])

    # A is not a member of B's project at all -> 404 on every path.
    get_resp = await client.get(
        f"/api/v1/projects/{project_b['id']}/requirements/{requirement_b['id']}", headers=user_a["headers"]
    )
    assert get_resp.status_code == 404

    list_resp = await client.get(
        f"/api/v1/projects/{project_b['id']}/requirements", headers=user_a["headers"]
    )
    assert list_resp.status_code == 404

    patch_resp = await client.patch(
        f"/api/v1/projects/{project_b['id']}/requirements/{requirement_b['id']}",
        json={"title": "Hijacked"},
        headers=user_a["headers"],
    )
    assert patch_resp.status_code == 404

    delete_resp = await client.delete(
        f"/api/v1/projects/{project_b['id']}/requirements/{requirement_b['id']}", headers=user_a["headers"]
    )
    assert delete_resp.status_code == 404

    # B's requirement is unaffected.
    still_there = await client.get(
        f"/api/v1/projects/{project_b['id']}/requirements/{requirement_b['id']}", headers=user_b["headers"]
    )
    assert still_there.status_code == 200


async def test_requirement_id_from_project_a_not_reachable_via_project_b(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    """Even a user who is a member of BOTH projects cannot address project A's
    requirement through project B's URL - project_id + requirement_id must match."""
    owner = await register_user()
    project_a = await _create_project(client, owner["headers"], "Project A")
    project_b = await _create_project(client, owner["headers"], "Project B")
    requirement_a = await _create_requirement(client, owner["headers"], project_a["id"])

    resp = await client.get(
        f"/api/v1/projects/{project_b['id']}/requirements/{requirement_a['id']}", headers=owner["headers"]
    )
    assert resp.status_code == 404
