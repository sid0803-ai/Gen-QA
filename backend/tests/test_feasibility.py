"""Tests for /api/v1/projects/{project_id}/requirements/{requirement_id}/feasibility/*
: mock feasibility-study generation, human override via edit-while-draft,
approve/reject lifecycle, role enforcement, and latest_feasibility_status on
the requirement list/detail endpoints. Mirrors test_ai_analysis.py's
structure."""
from collections.abc import Awaitable, Callable

from httpx import AsyncClient

PAYLOAD_KEYS = {"summary", "scenarios"}
SCENARIO_KEYS = {"title", "description", "recommendation", "reason", "overridden_recommendation"}


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
    title: str = "Users can log in with a CAPTCHA challenge",
    description: str = (
        "As a user, I want to log in with my email and password, and complete a CAPTCHA "
        "challenge, so that automated bots cannot brute-force accounts."
    ),
    **extra,
) -> dict:
    body = {"title": title, "description": description, **extra}
    resp = await client.post(
        f"/api/v1/projects/{project_id}/requirements", json=body, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _base(project_id: str, requirement_id: str) -> str:
    return f"/api/v1/projects/{project_id}/requirements/{requirement_id}/feasibility"


async def test_trigger_feasibility_creates_draft_with_full_payload(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])

    resp = await client.post(_base(project["id"], requirement["id"]), headers=owner["headers"])
    assert resp.status_code == 201, resp.text
    feasibility = resp.json()

    assert feasibility["requirement_id"] == requirement["id"]
    assert feasibility["status"] == "draft"
    assert feasibility["created_by"] == owner["user"]["id"]
    assert feasibility["approved_by"] is None
    assert feasibility["approved_at"] is None

    payload = feasibility["payload"]
    assert set(payload.keys()) == PAYLOAD_KEYS
    assert payload["summary"]
    assert len(payload["scenarios"]) >= 1
    for scenario in payload["scenarios"]:
        assert set(scenario.keys()) == SCENARIO_KEYS
        assert scenario["title"]
        assert scenario["description"]
        assert scenario["reason"]
        assert scenario["recommendation"] in ("automate", "manual", "hybrid", "needs_review")
        # Human override starts unset - the AI's own recommendation is never
        # pre-overwritten.
        assert scenario["overridden_recommendation"] is None

    # This requirement's text mentions "CAPTCHA" -> mock should surface a
    # CAPTCHA-specific scenario (proves content varies with input).
    titles = " ".join(s["title"] for s in payload["scenarios"]).lower()
    assert "captcha" in titles


async def test_feasibility_varies_with_requirement_content(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    req1 = await _create_requirement(
        client,
        owner["headers"],
        project["id"],
        title="Third-party payment gateway webhook",
        description="Integrate with an external third-party payment gateway webhook for settlement notifications.",
    )
    req2 = await _create_requirement(
        client,
        owner["headers"],
        project["id"],
        title="Redesign dashboard layout",
        description="Improve visual layout and look and feel of the analytics dashboard for usability.",
    )

    resp1 = await client.post(_base(project["id"], req1["id"]), headers=owner["headers"])
    resp2 = await client.post(_base(project["id"], req2["id"]), headers=owner["headers"])
    assert resp1.status_code == 201 and resp2.status_code == 201

    assert resp1.json()["payload"]["summary"] != resp2.json()["payload"]["summary"]
    assert resp1.json()["payload"]["scenarios"] != resp2.json()["payload"]["scenarios"]


async def test_trigger_feasibility_role_enforcement(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    viewer = await register_user()
    await _add_member(client, owner["headers"], project["id"], viewer["email"], "viewer")
    stranger = await register_user()

    viewer_resp = await client.post(_base(project["id"], requirement["id"]), headers=viewer["headers"])
    assert viewer_resp.status_code == 403

    stranger_resp = await client.post(_base(project["id"], requirement["id"]), headers=stranger["headers"])
    assert stranger_resp.status_code == 404


async def test_list_and_get_feasibility_studies(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])

    created = await client.post(_base(project["id"], requirement["id"]), headers=owner["headers"])
    feasibility_id = created.json()["id"]

    listing = await client.get(_base(project["id"], requirement["id"]), headers=owner["headers"])
    assert listing.status_code == 200
    items = listing.json()
    assert len(items) == 1
    assert "payload" not in items[0]  # list form omits payload by design

    detail = await client.get(
        f"{_base(project['id'], requirement['id'])}/{feasibility_id}", headers=owner["headers"]
    )
    assert detail.status_code == 200
    assert "payload" in detail.json()

    viewer = await register_user()
    await _add_member(client, owner["headers"], project["id"], viewer["email"], "viewer")
    viewer_list = await client.get(_base(project["id"], requirement["id"]), headers=viewer["headers"])
    assert viewer_list.status_code == 200


async def test_get_feasibility_nonexistent_returns_404(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])

    resp = await client.get(
        f"{_base(project['id'], requirement['id'])}/00000000-0000-0000-0000-000000000000",
        headers=owner["headers"],
    )
    assert resp.status_code == 404


async def test_approve_lifecycle_with_human_override(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])

    created = await client.post(_base(project["id"], requirement["id"]), headers=owner["headers"])
    feasibility = created.json()
    feasibility_id = feasibility["id"]
    base = _base(project["id"], requirement["id"])

    # Human overrides one scenario's recommendation while draft, without
    # touching the AI's original `recommendation`.
    edited_payload = dict(feasibility["payload"])
    edited_payload["scenarios"] = [dict(s) for s in edited_payload["scenarios"]]
    original_recommendation = edited_payload["scenarios"][0]["recommendation"]
    override_value = "manual" if original_recommendation != "manual" else "automate"
    edited_payload["scenarios"][0]["overridden_recommendation"] = override_value

    edit_resp = await client.patch(
        f"{base}/{feasibility_id}", json={"payload": edited_payload}, headers=owner["headers"]
    )
    assert edit_resp.status_code == 200
    edited = edit_resp.json()
    assert edited["status"] == "draft"
    assert edited["payload"]["scenarios"][0]["overridden_recommendation"] == override_value
    # AI's original recommendation remains visible/untouched.
    assert edited["payload"]["scenarios"][0]["recommendation"] == original_recommendation

    # Approve succeeds.
    approve_resp = await client.post(f"{base}/{feasibility_id}/approve", headers=owner["headers"])
    assert approve_resp.status_code == 200
    approved = approve_resp.json()
    assert approved["status"] == "approved"
    assert approved["approved_by"] == owner["user"]["id"]
    assert approved["approved_at"] is not None

    # Editing an approved feasibility study is no longer allowed.
    edit_again = await client.patch(
        f"{base}/{feasibility_id}", json={"payload": edited_payload}, headers=owner["headers"]
    )
    assert edit_again.status_code == 409

    # Approving again is no longer allowed.
    approve_again = await client.post(f"{base}/{feasibility_id}/approve", headers=owner["headers"])
    assert approve_again.status_code == 409

    # Rejecting an already-approved feasibility study is also not allowed.
    reject_after_approve = await client.post(f"{base}/{feasibility_id}/reject", headers=owner["headers"])
    assert reject_after_approve.status_code == 409


async def test_reject_lifecycle(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])

    created = await client.post(_base(project["id"], requirement["id"]), headers=owner["headers"])
    feasibility_id = created.json()["id"]
    base = _base(project["id"], requirement["id"])

    reject_resp = await client.post(f"{base}/{feasibility_id}/reject", headers=owner["headers"])
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "rejected"

    edit_again = await client.patch(
        f"{base}/{feasibility_id}",
        json={"payload": created.json()["payload"]},
        headers=owner["headers"],
    )
    assert edit_again.status_code == 409

    reject_again = await client.post(f"{base}/{feasibility_id}/reject", headers=owner["headers"])
    assert reject_again.status_code == 409

    approve_after_reject = await client.post(f"{base}/{feasibility_id}/approve", headers=owner["headers"])
    assert approve_after_reject.status_code == 409


async def test_feasibility_write_actions_require_member_role(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    viewer = await register_user()
    await _add_member(client, owner["headers"], project["id"], viewer["email"], "viewer")

    created = await client.post(_base(project["id"], requirement["id"]), headers=owner["headers"])
    feasibility = created.json()
    base = _base(project["id"], requirement["id"])

    edit_resp = await client.patch(
        f"{base}/{feasibility['id']}", json={"payload": feasibility["payload"]}, headers=viewer["headers"]
    )
    assert edit_resp.status_code == 403

    approve_resp = await client.post(f"{base}/{feasibility['id']}/approve", headers=viewer["headers"])
    assert approve_resp.status_code == 403

    reject_resp = await client.post(f"{base}/{feasibility['id']}/reject", headers=viewer["headers"])
    assert reject_resp.status_code == 403


async def test_second_feasibility_does_not_affect_first(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    base = _base(project["id"], requirement["id"])

    first = await client.post(base, headers=owner["headers"])
    first_id = first.json()["id"]

    await client.post(f"{base}/{first_id}/approve", headers=owner["headers"])

    second = await client.post(base, headers=owner["headers"])
    assert second.status_code == 201
    second_id = second.json()["id"]
    assert second.json()["status"] == "draft"
    assert second_id != first_id

    first_detail = await client.get(f"{base}/{first_id}", headers=owner["headers"])
    assert first_detail.json()["status"] == "approved"

    listing = await client.get(base, headers=owner["headers"])
    items = listing.json()
    assert len(items) == 2
    assert items[0]["id"] == second_id
    assert items[1]["id"] == first_id


async def test_latest_feasibility_status_reflects_most_recent(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    base = _base(project["id"], requirement["id"])

    def _latest_status_in_list(items: list[dict], requirement_id: str) -> str:
        matches = [i for i in items if i["id"] == requirement_id]
        assert len(matches) == 1
        return matches[0]["latest_feasibility_status"]

    async def _list_status() -> str:
        resp = await client.get(
            f"/api/v1/projects/{project['id']}/requirements", headers=owner["headers"]
        )
        return _latest_status_in_list(resp.json(), requirement["id"])

    async def _detail_status() -> str:
        resp = await client.get(
            f"/api/v1/projects/{project['id']}/requirements/{requirement['id']}", headers=owner["headers"]
        )
        assert resp.status_code == 200
        return resp.json()["latest_feasibility_status"]

    assert await _list_status() == "none"
    assert await _detail_status() == "none"

    first = await client.post(base, headers=owner["headers"])
    first_id = first.json()["id"]
    assert await _list_status() == "draft"
    assert await _detail_status() == "draft"

    await client.post(f"{base}/{first_id}/approve", headers=owner["headers"])
    assert await _list_status() == "approved"
    assert await _detail_status() == "approved"

    # A brand-new (second) feasibility study flips the latest status back to
    # draft, even though the first remains approved in history.
    second = await client.post(base, headers=owner["headers"])
    second_id = second.json()["id"]
    assert await _list_status() == "draft"
    assert await _detail_status() == "draft"

    await client.post(f"{base}/{second_id}/reject", headers=owner["headers"])
    assert await _list_status() == "rejected"
    assert await _detail_status() == "rejected"


async def test_project_isolation_feasibility_unreachable_from_other_project(
    user_a: dict, user_b: dict, client: AsyncClient
) -> None:
    project_b = await _create_project(client, user_b["headers"], "B's project")
    requirement_b = await _create_requirement(client, user_b["headers"], project_b["id"])
    base_b = _base(project_b["id"], requirement_b["id"])
    created = await client.post(base_b, headers=user_b["headers"])
    feasibility_id = created.json()["id"]

    assert (await client.get(base_b, headers=user_a["headers"])).status_code == 404
    assert (await client.get(f"{base_b}/{feasibility_id}", headers=user_a["headers"])).status_code == 404
    assert (await client.post(base_b, headers=user_a["headers"])).status_code == 404
    assert (
        await client.patch(
            f"{base_b}/{feasibility_id}", json={"payload": created.json()["payload"]}, headers=user_a["headers"]
        )
    ).status_code == 404
    assert (await client.post(f"{base_b}/{feasibility_id}/approve", headers=user_a["headers"])).status_code == 404
    assert (await client.post(f"{base_b}/{feasibility_id}/reject", headers=user_a["headers"])).status_code == 404
