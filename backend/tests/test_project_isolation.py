"""Critical isolation guarantee: user A must never see or access user B's
project, whether through the list endpoint or by guessing/knowing a direct
project id. Non-membership must surface as 404, never 403, so existence of
another user's project is never leaked.
"""
from collections.abc import Awaitable, Callable

from httpx import AsyncClient


async def _create_project(client: AsyncClient, headers: dict, name: str) -> dict:
    resp = await client.post("/api/v1/projects", json={"name": name}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_user_a_cannot_get_user_b_project_detail(user_a: dict, user_b: dict, client: AsyncClient) -> None:
    project_b = await _create_project(client, user_b["headers"], "B's project")

    resp = await client.get(f"/api/v1/projects/{project_b['id']}", headers=user_a["headers"])
    assert resp.status_code == 404


async def test_user_a_cannot_list_user_b_project_members(
    user_a: dict, user_b: dict, client: AsyncClient
) -> None:
    project_b = await _create_project(client, user_b["headers"], "B's project")

    resp = await client.get(
        f"/api/v1/projects/{project_b['id']}/members", headers=user_a["headers"]
    )
    assert resp.status_code == 404


async def test_user_a_cannot_update_user_b_project(user_a: dict, user_b: dict, client: AsyncClient) -> None:
    project_b = await _create_project(client, user_b["headers"], "B's project")

    resp = await client.patch(
        f"/api/v1/projects/{project_b['id']}",
        json={"name": "Hijacked"},
        headers=user_a["headers"],
    )
    assert resp.status_code == 404


async def test_user_a_cannot_delete_user_b_project(user_a: dict, user_b: dict, client: AsyncClient) -> None:
    project_b = await _create_project(client, user_b["headers"], "B's project")

    resp = await client.delete(f"/api/v1/projects/{project_b['id']}", headers=user_a["headers"])
    assert resp.status_code == 404

    # B can still see their own project: it was never actually deleted.
    still_there = await client.get(f"/api/v1/projects/{project_b['id']}", headers=user_b["headers"])
    assert still_there.status_code == 200


async def test_user_a_cannot_add_members_to_user_b_project(
    user_a: dict, user_b: dict, client: AsyncClient
) -> None:
    project_b = await _create_project(client, user_b["headers"], "B's project")

    resp = await client.post(
        f"/api/v1/projects/{project_b['id']}/members",
        json={"email": user_a["email"], "role": "admin"},
        headers=user_a["headers"],
    )
    assert resp.status_code == 404


async def test_list_projects_never_includes_other_users_projects(
    user_a: dict, user_b: dict, client: AsyncClient
) -> None:
    project_a = await _create_project(client, user_a["headers"], "A's project")
    await _create_project(client, user_b["headers"], "B's project 1")
    await _create_project(client, user_b["headers"], "B's project 2")

    resp = await client.get("/api/v1/projects", headers=user_a["headers"])
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()]
    assert ids == [project_a["id"]]


async def test_user_a_project_ids_never_leak_via_member_management(
    user_a: dict, user_b: dict, client: AsyncClient
) -> None:
    """Even role-management sub-actions on B's project must 404 for A."""
    project_b = await _create_project(client, user_b["headers"], "B's project")

    role_update = await client.patch(
        f"/api/v1/projects/{project_b['id']}/members/{user_b['user']['id']}",
        json={"role": "member"},
        headers=user_a["headers"],
    )
    assert role_update.status_code == 404

    removal = await client.delete(
        f"/api/v1/projects/{project_b['id']}/members/{user_b['user']['id']}",
        headers=user_a["headers"],
    )
    assert removal.status_code == 404
