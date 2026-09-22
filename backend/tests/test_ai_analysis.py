"""Tests for /api/v1/projects/{project_id}/requirements/{requirement_id}/analyses/*
: mock AI analysis generation, edit-while-draft, approve/reject lifecycle,
role enforcement, and latest_analysis_status on the requirement list."""
from collections.abc import Awaitable, Callable

from httpx import AsyncClient

PAYLOAD_KEYS = {
    "summary",
    "business_rules",
    "functional_conditions",
    "risks",
    "ambiguities",
    "missing_information",
    "edge_cases",
    "automation_candidates",
    "manual_candidates",
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
    title: str = "Users can pay their invoice online",
    description: str = (
        "As a customer, I want to pay my invoice online with a credit card so that I don't "
        "have to mail a check. The payment should be processed quickly."
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
    return f"/api/v1/projects/{project_id}/requirements/{requirement_id}/analyses"


async def test_trigger_analysis_creates_draft_with_full_payload(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])

    resp = await client.post(_base(project["id"], requirement["id"]), headers=owner["headers"])
    assert resp.status_code == 201, resp.text
    analysis = resp.json()

    assert analysis["requirement_id"] == requirement["id"]
    assert analysis["status"] == "draft"
    assert analysis["created_by"] == owner["user"]["id"]
    assert analysis["approved_by"] is None
    assert analysis["approved_at"] is None

    payload = analysis["payload"]
    assert set(payload.keys()) == PAYLOAD_KEYS
    assert requirement["title"] in payload["summary"]
    for list_field in [
        "business_rules",
        "functional_conditions",
        "risks",
        "ambiguities",
        "missing_information",
        "edge_cases",
        "automation_candidates",
        "manual_candidates",
    ]:
        assert len(payload[list_field]) >= 1, f"{list_field} should be non-empty"

    # This requirement's text mentions "payment"/"credit card" -> mock should
    # surface a payment-related risk (proves content varies with input).
    risk_statements = " ".join(r["statement"] for r in payload["risks"]).lower()
    assert "payment" in risk_statements or "financial" in risk_statements


async def test_analysis_varies_with_requirement_content(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    req1 = await _create_requirement(
        client, owner["headers"], project["id"], title="Reset password", description="User resets password via email."
    )
    req2 = await _create_requirement(
        client,
        owner["headers"],
        project["id"],
        title="Export analytics report",
        description="Admin exports a dashboard report as CSV.",
    )

    resp1 = await client.post(_base(project["id"], req1["id"]), headers=owner["headers"])
    resp2 = await client.post(_base(project["id"], req2["id"]), headers=owner["headers"])
    assert resp1.status_code == 201 and resp2.status_code == 201

    assert resp1.json()["payload"]["summary"] != resp2.json()["payload"]["summary"]


async def test_trigger_analysis_role_enforcement(
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


async def test_list_and_get_analyses(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])

    created = await client.post(_base(project["id"], requirement["id"]), headers=owner["headers"])
    analysis_id = created.json()["id"]

    listing = await client.get(_base(project["id"], requirement["id"]), headers=owner["headers"])
    assert listing.status_code == 200
    items = listing.json()
    assert len(items) == 1
    assert "payload" not in items[0]  # list form omits payload by design

    detail = await client.get(f"{_base(project['id'], requirement['id'])}/{analysis_id}", headers=owner["headers"])
    assert detail.status_code == 200
    assert "payload" in detail.json()

    viewer = await register_user()
    await _add_member(client, owner["headers"], project["id"], viewer["email"], "viewer")
    viewer_list = await client.get(_base(project["id"], requirement["id"]), headers=viewer["headers"])
    assert viewer_list.status_code == 200


async def test_get_analysis_nonexistent_returns_404(
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


async def test_approve_lifecycle(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])

    created = await client.post(_base(project["id"], requirement["id"]), headers=owner["headers"])
    analysis = created.json()
    analysis_id = analysis["id"]
    base = _base(project["id"], requirement["id"])

    # Edit while draft succeeds.
    edited_payload = dict(analysis["payload"])
    edited_payload["summary"] = "Edited summary by a human reviewer."
    edit_resp = await client.patch(
        f"{base}/{analysis_id}", json={"payload": edited_payload}, headers=owner["headers"]
    )
    assert edit_resp.status_code == 200
    assert edit_resp.json()["payload"]["summary"] == "Edited summary by a human reviewer."
    assert edit_resp.json()["status"] == "draft"

    # Approve succeeds.
    approve_resp = await client.post(f"{base}/{analysis_id}/approve", headers=owner["headers"])
    assert approve_resp.status_code == 200
    approved = approve_resp.json()
    assert approved["status"] == "approved"
    assert approved["approved_by"] == owner["user"]["id"]
    assert approved["approved_at"] is not None

    # Editing an approved analysis is no longer allowed.
    edit_again = await client.patch(
        f"{base}/{analysis_id}", json={"payload": edited_payload}, headers=owner["headers"]
    )
    assert edit_again.status_code == 409

    # Approving again is no longer allowed.
    approve_again = await client.post(f"{base}/{analysis_id}/approve", headers=owner["headers"])
    assert approve_again.status_code == 409

    # Rejecting an already-approved analysis is also not allowed.
    reject_after_approve = await client.post(f"{base}/{analysis_id}/reject", headers=owner["headers"])
    assert reject_after_approve.status_code == 409


async def test_reject_lifecycle(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])

    created = await client.post(_base(project["id"], requirement["id"]), headers=owner["headers"])
    analysis_id = created.json()["id"]
    base = _base(project["id"], requirement["id"])

    reject_resp = await client.post(f"{base}/{analysis_id}/reject", headers=owner["headers"])
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "rejected"

    edit_again = await client.patch(
        f"{base}/{analysis_id}",
        json={"payload": created.json()["payload"]},
        headers=owner["headers"],
    )
    assert edit_again.status_code == 409

    reject_again = await client.post(f"{base}/{analysis_id}/reject", headers=owner["headers"])
    assert reject_again.status_code == 409

    approve_after_reject = await client.post(f"{base}/{analysis_id}/approve", headers=owner["headers"])
    assert approve_after_reject.status_code == 409


async def test_analysis_write_actions_require_member_role(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    viewer = await register_user()
    await _add_member(client, owner["headers"], project["id"], viewer["email"], "viewer")

    created = await client.post(_base(project["id"], requirement["id"]), headers=owner["headers"])
    analysis = created.json()
    base = _base(project["id"], requirement["id"])

    edit_resp = await client.patch(
        f"{base}/{analysis['id']}", json={"payload": analysis["payload"]}, headers=viewer["headers"]
    )
    assert edit_resp.status_code == 403

    approve_resp = await client.post(f"{base}/{analysis['id']}/approve", headers=viewer["headers"])
    assert approve_resp.status_code == 403

    reject_resp = await client.post(f"{base}/{analysis['id']}/reject", headers=viewer["headers"])
    assert reject_resp.status_code == 403


async def test_second_analysis_does_not_affect_first(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    base = _base(project["id"], requirement["id"])

    first = await client.post(base, headers=owner["headers"])
    first_id = first.json()["id"]

    # Approve the first one.
    await client.post(f"{base}/{first_id}/approve", headers=owner["headers"])

    # Trigger a second, independent analysis.
    second = await client.post(base, headers=owner["headers"])
    assert second.status_code == 201
    second_id = second.json()["id"]
    assert second.json()["status"] == "draft"
    assert second_id != first_id

    # The first analysis is untouched by the second being created.
    first_detail = await client.get(f"{base}/{first_id}", headers=owner["headers"])
    assert first_detail.json()["status"] == "approved"

    listing = await client.get(base, headers=owner["headers"])
    items = listing.json()
    assert len(items) == 2
    # Newest first.
    assert items[0]["id"] == second_id
    assert items[1]["id"] == first_id


async def test_latest_analysis_status_reflects_most_recent(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    base = _base(project["id"], requirement["id"])

    def _latest_status(items: list[dict], requirement_id: str) -> str:
        matches = [i for i in items if i["id"] == requirement_id]
        assert len(matches) == 1
        return matches[0]["latest_analysis_status"]

    listing_resp = await client.get(
        f"/api/v1/projects/{project['id']}/requirements", headers=owner["headers"]
    )
    assert _latest_status(listing_resp.json(), requirement["id"]) == "none"

    first = await client.post(base, headers=owner["headers"])
    first_id = first.json()["id"]
    listing_resp = await client.get(
        f"/api/v1/projects/{project['id']}/requirements", headers=owner["headers"]
    )
    assert _latest_status(listing_resp.json(), requirement["id"]) == "draft"

    await client.post(f"{base}/{first_id}/approve", headers=owner["headers"])
    listing_resp = await client.get(
        f"/api/v1/projects/{project['id']}/requirements", headers=owner["headers"]
    )
    assert _latest_status(listing_resp.json(), requirement["id"]) == "approved"

    # A brand-new (second) analysis flips the latest status back to draft,
    # even though the first one remains approved in history.
    second = await client.post(base, headers=owner["headers"])
    second_id = second.json()["id"]
    listing_resp = await client.get(
        f"/api/v1/projects/{project['id']}/requirements", headers=owner["headers"]
    )
    assert _latest_status(listing_resp.json(), requirement["id"]) == "draft"

    await client.post(f"{base}/{second_id}/reject", headers=owner["headers"])
    listing_resp = await client.get(
        f"/api/v1/projects/{project['id']}/requirements", headers=owner["headers"]
    )
    assert _latest_status(listing_resp.json(), requirement["id"]) == "rejected"


async def test_project_isolation_analyses_unreachable_from_other_project(
    user_a: dict, user_b: dict, client: AsyncClient
) -> None:
    project_b = await _create_project(client, user_b["headers"], "B's project")
    requirement_b = await _create_requirement(client, user_b["headers"], project_b["id"])
    base_b = _base(project_b["id"], requirement_b["id"])
    created = await client.post(base_b, headers=user_b["headers"])
    analysis_id = created.json()["id"]

    assert (await client.get(base_b, headers=user_a["headers"])).status_code == 404
    assert (await client.get(f"{base_b}/{analysis_id}", headers=user_a["headers"])).status_code == 404
    assert (await client.post(base_b, headers=user_a["headers"])).status_code == 404
    assert (
        await client.patch(
            f"{base_b}/{analysis_id}", json={"payload": created.json()["payload"]}, headers=user_a["headers"]
        )
    ).status_code == 404
    assert (await client.post(f"{base_b}/{analysis_id}/approve", headers=user_a["headers"])).status_code == 404
    assert (await client.post(f"{base_b}/{analysis_id}/reject", headers=user_a["headers"])).status_code == 404
