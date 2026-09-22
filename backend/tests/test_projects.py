"""Tests for /api/v1/projects/* : CRUD, membership, and role enforcement."""
from collections.abc import Awaitable, Callable

from httpx import AsyncClient


async def _create_project(client: AsyncClient, headers: dict, name: str = "Project X", description: str | None = "desc") -> dict:
    resp = await client.post(
        "/api/v1/projects", json={"name": name, "description": description}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_create_project_makes_creator_admin(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"], name="Alpha")
    assert project["name"] == "Alpha"
    assert project["description"] == "desc"
    assert "id" in project and "created_at" in project

    listing = await client.get("/api/v1/projects", headers=owner["headers"])
    assert listing.status_code == 200
    items = listing.json()
    assert len(items) == 1
    assert items[0]["id"] == project["id"]
    assert items[0]["role"] == "admin"


async def test_list_projects_only_shows_own_projects(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    other = await register_user()
    await _create_project(client, owner["headers"], name="Owner project")
    await _create_project(client, other["headers"], name="Other project")

    resp = await client.get("/api/v1/projects", headers=owner["headers"])
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert names == ["Owner project"]


async def test_get_project_detail_as_member(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])

    resp = await client.get(f"/api/v1/projects/{project['id']}", headers=owner["headers"])
    assert resp.status_code == 200
    assert resp.json()["id"] == project["id"]


async def test_get_project_detail_nonexistent_returns_404(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    resp = await client.get(
        "/api/v1/projects/00000000-0000-0000-0000-000000000000", headers=owner["headers"]
    )
    assert resp.status_code == 404


async def test_update_project_requires_admin(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])

    member = await register_user()
    add_resp = await client.post(
        f"/api/v1/projects/{project['id']}/members",
        json={"email": member["email"], "role": "member"},
        headers=owner["headers"],
    )
    assert add_resp.status_code == 201

    forbidden = await client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"name": "Renamed"},
        headers=member["headers"],
    )
    assert forbidden.status_code == 403

    ok = await client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"name": "Renamed"},
        headers=owner["headers"],
    )
    assert ok.status_code == 200
    assert ok.json()["name"] == "Renamed"


async def test_update_project_not_a_member_returns_404(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    stranger = await register_user()
    project = await _create_project(client, owner["headers"])

    resp = await client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"name": "Nope"},
        headers=stranger["headers"],
    )
    assert resp.status_code == 404


async def test_delete_project_requires_admin_then_deletes(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])

    member = await register_user()
    await client.post(
        f"/api/v1/projects/{project['id']}/members",
        json={"email": member["email"], "role": "viewer"},
        headers=owner["headers"],
    )

    forbidden = await client.delete(f"/api/v1/projects/{project['id']}", headers=member["headers"])
    assert forbidden.status_code == 403

    ok = await client.delete(f"/api/v1/projects/{project['id']}", headers=owner["headers"])
    assert ok.status_code == 204

    gone = await client.get(f"/api/v1/projects/{project['id']}", headers=owner["headers"])
    assert gone.status_code == 404


async def test_list_members_requires_membership(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])

    resp = await client.get(f"/api/v1/projects/{project['id']}/members", headers=owner["headers"])
    assert resp.status_code == 200
    members = resp.json()
    assert len(members) == 1
    assert members[0]["role"] == "admin"
    assert members[0]["email"] == owner["email"]


async def test_add_member_unknown_email_returns_404(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])

    resp = await client.post(
        f"/api/v1/projects/{project['id']}/members",
        json={"email": "ghost@example.com", "role": "member"},
        headers=owner["headers"],
    )
    assert resp.status_code == 404


async def test_add_member_twice_returns_409(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    member = await register_user()

    first = await client.post(
        f"/api/v1/projects/{project['id']}/members",
        json={"email": member["email"], "role": "member"},
        headers=owner["headers"],
    )
    assert first.status_code == 201

    second = await client.post(
        f"/api/v1/projects/{project['id']}/members",
        json={"email": member["email"], "role": "viewer"},
        headers=owner["headers"],
    )
    assert second.status_code == 409


async def test_add_member_requires_admin(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    member = await register_user()
    third = await register_user()

    await client.post(
        f"/api/v1/projects/{project['id']}/members",
        json={"email": member["email"], "role": "member"},
        headers=owner["headers"],
    )

    resp = await client.post(
        f"/api/v1/projects/{project['id']}/members",
        json={"email": third["email"], "role": "member"},
        headers=member["headers"],
    )
    assert resp.status_code == 403


async def test_update_member_role(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    member = await register_user()

    await client.post(
        f"/api/v1/projects/{project['id']}/members",
        json={"email": member["email"], "role": "viewer"},
        headers=owner["headers"],
    )

    resp = await client.patch(
        f"/api/v1/projects/{project['id']}/members/{member['user']['id']}",
        json={"role": "member"},
        headers=owner["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "member"


async def test_last_admin_cannot_demote_self(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])

    resp = await client.patch(
        f"/api/v1/projects/{project['id']}/members/{owner['user']['id']}",
        json={"role": "member"},
        headers=owner["headers"],
    )
    assert resp.status_code == 409


async def test_last_admin_cannot_be_removed(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])

    resp = await client.delete(
        f"/api/v1/projects/{project['id']}/members/{owner['user']['id']}",
        headers=owner["headers"],
    )
    assert resp.status_code == 409


async def test_second_admin_allows_first_to_be_demoted(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    second = await register_user()

    await client.post(
        f"/api/v1/projects/{project['id']}/members",
        json={"email": second["email"], "role": "admin"},
        headers=owner["headers"],
    )

    resp = await client.patch(
        f"/api/v1/projects/{project['id']}/members/{owner['user']['id']}",
        json={"role": "member"},
        headers=owner["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "member"


async def test_remove_member(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    member = await register_user()

    await client.post(
        f"/api/v1/projects/{project['id']}/members",
        json={"email": member["email"], "role": "member"},
        headers=owner["headers"],
    )

    resp = await client.delete(
        f"/api/v1/projects/{project['id']}/members/{member['user']['id']}",
        headers=owner["headers"],
    )
    assert resp.status_code == 204

    listing = await client.get(f"/api/v1/projects/{project['id']}/members", headers=owner["headers"])
    emails = [m["email"] for m in listing.json()]
    assert member["email"] not in emails
