"""Tests for /api/v1/projects/{project_id}/environments/* (environments
domain): CRUD, role enforcement (viewer read-only, member create/edit, admin
delete), and project isolation.
"""
from collections.abc import Awaitable, Callable

from httpx import AsyncClient

READ_KEYS = {
    "id",
    "project_id",
    "name",
    "base_url",
    "variables",
    "created_by",
    "created_at",
    "updated_at",
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


def _base(project_id: str) -> str:
    return f"/api/v1/projects/{project_id}/environments"


async def _create_environment(client: AsyncClient, headers: dict, project_id: str, **overrides) -> dict:
    body = {"name": "Staging", "base_url": "https://staging.example.com", "variables": {"FOO": "bar"}}
    body.update(overrides)
    resp = await client.post(_base(project_id), json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_create_environment_full_shape(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])

    environment = await _create_environment(client, owner["headers"], project["id"])
    assert set(environment.keys()) == READ_KEYS
    assert environment["name"] == "Staging"
    assert environment["base_url"] == "https://staging.example.com"
    assert environment["variables"] == {"FOO": "bar"}
    assert environment["project_id"] == project["id"]
    assert environment["created_by"] == owner["user"]["id"]


async def test_variables_default_to_empty_dict(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])

    resp = await client.post(
        _base(project["id"]),
        json={"name": "Prod", "base_url": "https://prod.example.com"},
        headers=owner["headers"],
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["variables"] == {}


async def test_list_and_get(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    env = await _create_environment(client, owner["headers"], project["id"])

    list_resp = await client.get(_base(project["id"]), headers=owner["headers"])
    assert list_resp.status_code == 200
    assert [e["id"] for e in list_resp.json()] == [env["id"]]

    get_resp = await client.get(f"{_base(project['id'])}/{env['id']}", headers=owner["headers"])
    assert get_resp.status_code == 200
    assert get_resp.json() == env


async def test_patch_updates_fields(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    env = await _create_environment(client, owner["headers"], project["id"])

    patch_resp = await client.patch(
        f"{_base(project['id'])}/{env['id']}",
        json={"base_url": "https://new.example.com", "variables": {"BAZ": "qux"}},
        headers=owner["headers"],
    )
    assert patch_resp.status_code == 200
    updated = patch_resp.json()
    assert updated["base_url"] == "https://new.example.com"
    assert updated["variables"] == {"BAZ": "qux"}
    assert updated["name"] == "Staging"  # untouched


async def test_role_enforcement(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    viewer = await register_user()
    await _add_member(client, owner["headers"], project["id"], viewer["email"], "viewer")
    member = await register_user()
    await _add_member(client, owner["headers"], project["id"], member["email"], "member")
    stranger = await register_user()

    create_viewer = await client.post(
        _base(project["id"]),
        json={"name": "Staging", "base_url": "https://staging.example.com"},
        headers=viewer["headers"],
    )
    assert create_viewer.status_code == 403

    list_stranger = await client.get(_base(project["id"]), headers=stranger["headers"])
    assert list_stranger.status_code == 404

    env = await _create_environment(client, owner["headers"], project["id"])

    patch_viewer = await client.patch(
        f"{_base(project['id'])}/{env['id']}", json={"name": "x"}, headers=viewer["headers"]
    )
    assert patch_viewer.status_code == 403

    delete_member = await client.delete(f"{_base(project['id'])}/{env['id']}", headers=member["headers"])
    assert delete_member.status_code == 403

    delete_admin = await client.delete(f"{_base(project['id'])}/{env['id']}", headers=owner["headers"])
    assert delete_admin.status_code == 204

    get_after_delete = await client.get(f"{_base(project['id'])}/{env['id']}", headers=owner["headers"])
    assert get_after_delete.status_code == 404


async def test_project_isolation(
    user_a: dict, user_b: dict, client: AsyncClient
) -> None:
    project_b = await _create_project(client, user_b["headers"], "B's project")
    env = await _create_environment(client, user_b["headers"], project_b["id"])
    base_b = _base(project_b["id"])

    assert (await client.get(base_b, headers=user_a["headers"])).status_code == 404
    assert (await client.get(f"{base_b}/{env['id']}", headers=user_a["headers"])).status_code == 404
    assert (
        await client.post(
            base_b, json={"name": "x", "base_url": "https://x.example.com"}, headers=user_a["headers"]
        )
    ).status_code == 404
    assert (
        await client.patch(f"{base_b}/{env['id']}", json={"name": "hijacked"}, headers=user_a["headers"])
    ).status_code == 404
    assert (await client.delete(f"{base_b}/{env['id']}", headers=user_a["headers"])).status_code == 404
