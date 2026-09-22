"""Tests for /api/v1/projects/{project_id}/requirements/{requirement_id}/strategy/*
: mock test-strategy generation, edit-while-draft, approve/reject lifecycle,
role enforcement, latest_strategy_status on the requirement list/detail
endpoints, and that generating a strategy after an approved feasibility
study actually uses that context. Mirrors test_ai_analysis.py's structure."""
from collections.abc import Awaitable, Callable

from httpx import AsyncClient

PAYLOAD_KEYS = {
    "summary",
    "levels",
    "environments",
    "test_data_requirements",
    "dependencies",
    "automation_scope_notes",
    "manual_scope_notes",
}
LEVEL_KEYS = {"level", "applicable", "estimated_scenario_count", "notes"}
VALID_LEVELS = {"functional", "api", "ui", "integration", "security", "performance", "regression"}


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
    title: str = "Users can pay their invoice online via a third-party payment gateway",
    description: str = (
        "As a customer, I want to pay my invoice online with a credit card through our "
        "third-party payment gateway integration so that I don't have to mail a check."
    ),
    **extra,
) -> dict:
    body = {"title": title, "description": description, **extra}
    resp = await client.post(
        f"/api/v1/projects/{project_id}/requirements", json=body, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _strategy_base(project_id: str, requirement_id: str) -> str:
    return f"/api/v1/projects/{project_id}/requirements/{requirement_id}/strategy"


def _feasibility_base(project_id: str, requirement_id: str) -> str:
    return f"/api/v1/projects/{project_id}/requirements/{requirement_id}/feasibility"


async def test_trigger_strategy_creates_draft_with_full_payload(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])

    resp = await client.post(_strategy_base(project["id"], requirement["id"]), headers=owner["headers"])
    assert resp.status_code == 201, resp.text
    strategy = resp.json()

    assert strategy["requirement_id"] == requirement["id"]
    assert strategy["status"] == "draft"
    assert strategy["created_by"] == owner["user"]["id"]
    assert strategy["approved_by"] is None
    assert strategy["approved_at"] is None

    payload = strategy["payload"]
    assert set(payload.keys()) == PAYLOAD_KEYS
    assert payload["summary"]
    assert payload["automation_scope_notes"]
    assert payload["manual_scope_notes"]
    assert len(payload["levels"]) >= 1
    seen_levels = set()
    for level in payload["levels"]:
        assert set(level.keys()) == LEVEL_KEYS
        assert level["level"] in VALID_LEVELS
        assert isinstance(level["applicable"], bool)
        assert isinstance(level["estimated_scenario_count"], int)
        assert level["notes"]
        seen_levels.add(level["level"])
    # functional and regression are always applicable/present.
    assert "functional" in seen_levels
    assert "regression" in seen_levels

    # This requirement mentions "third-party payment gateway" -> integration
    # and security levels should be surfaced as applicable (content varies
    # with input, proven more directly in the next test).
    assert len(payload["environments"]) >= 1
    assert len(payload["test_data_requirements"]) >= 1
    assert len(payload["dependencies"]) >= 1


async def test_strategy_varies_with_requirement_content(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    req1 = await _create_requirement(
        client,
        owner["headers"],
        project["id"],
        title="Reset password",
        description="User resets their password via a login form with real-time validation.",
    )
    req2 = await _create_requirement(
        client,
        owner["headers"],
        project["id"],
        title="Export analytics report",
        description="Admin exports a large dashboard report as CSV under heavy concurrent load.",
    )

    resp1 = await client.post(_strategy_base(project["id"], req1["id"]), headers=owner["headers"])
    resp2 = await client.post(_strategy_base(project["id"], req2["id"]), headers=owner["headers"])
    assert resp1.status_code == 201 and resp2.status_code == 201

    assert resp1.json()["payload"]["summary"] != resp2.json()["payload"]["summary"]


async def test_trigger_strategy_role_enforcement(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    viewer = await register_user()
    await _add_member(client, owner["headers"], project["id"], viewer["email"], "viewer")
    stranger = await register_user()

    viewer_resp = await client.post(_strategy_base(project["id"], requirement["id"]), headers=viewer["headers"])
    assert viewer_resp.status_code == 403

    stranger_resp = await client.post(_strategy_base(project["id"], requirement["id"]), headers=stranger["headers"])
    assert stranger_resp.status_code == 404


async def test_list_and_get_strategies(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])

    created = await client.post(_strategy_base(project["id"], requirement["id"]), headers=owner["headers"])
    strategy_id = created.json()["id"]

    listing = await client.get(_strategy_base(project["id"], requirement["id"]), headers=owner["headers"])
    assert listing.status_code == 200
    items = listing.json()
    assert len(items) == 1
    assert "payload" not in items[0]

    detail = await client.get(
        f"{_strategy_base(project['id'], requirement['id'])}/{strategy_id}", headers=owner["headers"]
    )
    assert detail.status_code == 200
    assert "payload" in detail.json()

    viewer = await register_user()
    await _add_member(client, owner["headers"], project["id"], viewer["email"], "viewer")
    viewer_list = await client.get(_strategy_base(project["id"], requirement["id"]), headers=viewer["headers"])
    assert viewer_list.status_code == 200


async def test_get_strategy_nonexistent_returns_404(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])

    resp = await client.get(
        f"{_strategy_base(project['id'], requirement['id'])}/00000000-0000-0000-0000-000000000000",
        headers=owner["headers"],
    )
    assert resp.status_code == 404


async def test_approve_lifecycle(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])

    created = await client.post(_strategy_base(project["id"], requirement["id"]), headers=owner["headers"])
    strategy = created.json()
    strategy_id = strategy["id"]
    base = _strategy_base(project["id"], requirement["id"])

    edited_payload = dict(strategy["payload"])
    edited_payload["summary"] = "Edited summary by a human reviewer."
    edit_resp = await client.patch(
        f"{base}/{strategy_id}", json={"payload": edited_payload}, headers=owner["headers"]
    )
    assert edit_resp.status_code == 200
    assert edit_resp.json()["payload"]["summary"] == "Edited summary by a human reviewer."
    assert edit_resp.json()["status"] == "draft"

    approve_resp = await client.post(f"{base}/{strategy_id}/approve", headers=owner["headers"])
    assert approve_resp.status_code == 200
    approved = approve_resp.json()
    assert approved["status"] == "approved"
    assert approved["approved_by"] == owner["user"]["id"]
    assert approved["approved_at"] is not None

    edit_again = await client.patch(
        f"{base}/{strategy_id}", json={"payload": edited_payload}, headers=owner["headers"]
    )
    assert edit_again.status_code == 409

    approve_again = await client.post(f"{base}/{strategy_id}/approve", headers=owner["headers"])
    assert approve_again.status_code == 409

    reject_after_approve = await client.post(f"{base}/{strategy_id}/reject", headers=owner["headers"])
    assert reject_after_approve.status_code == 409


async def test_reject_lifecycle(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])

    created = await client.post(_strategy_base(project["id"], requirement["id"]), headers=owner["headers"])
    strategy_id = created.json()["id"]
    base = _strategy_base(project["id"], requirement["id"])

    reject_resp = await client.post(f"{base}/{strategy_id}/reject", headers=owner["headers"])
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "rejected"

    edit_again = await client.patch(
        f"{base}/{strategy_id}",
        json={"payload": created.json()["payload"]},
        headers=owner["headers"],
    )
    assert edit_again.status_code == 409

    reject_again = await client.post(f"{base}/{strategy_id}/reject", headers=owner["headers"])
    assert reject_again.status_code == 409

    approve_after_reject = await client.post(f"{base}/{strategy_id}/approve", headers=owner["headers"])
    assert approve_after_reject.status_code == 409


async def test_strategy_write_actions_require_member_role(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    viewer = await register_user()
    await _add_member(client, owner["headers"], project["id"], viewer["email"], "viewer")

    created = await client.post(_strategy_base(project["id"], requirement["id"]), headers=owner["headers"])
    strategy = created.json()
    base = _strategy_base(project["id"], requirement["id"])

    edit_resp = await client.patch(
        f"{base}/{strategy['id']}", json={"payload": strategy["payload"]}, headers=viewer["headers"]
    )
    assert edit_resp.status_code == 403

    approve_resp = await client.post(f"{base}/{strategy['id']}/approve", headers=viewer["headers"])
    assert approve_resp.status_code == 403

    reject_resp = await client.post(f"{base}/{strategy['id']}/reject", headers=viewer["headers"])
    assert reject_resp.status_code == 403


async def test_second_strategy_does_not_affect_first(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    base = _strategy_base(project["id"], requirement["id"])

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


async def test_latest_strategy_status_reflects_most_recent(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    base = _strategy_base(project["id"], requirement["id"])

    def _latest_status_in_list(items: list[dict], requirement_id: str) -> str:
        matches = [i for i in items if i["id"] == requirement_id]
        assert len(matches) == 1
        return matches[0]["latest_strategy_status"]

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
        return resp.json()["latest_strategy_status"]

    assert await _list_status() == "none"
    assert await _detail_status() == "none"

    first = await client.post(base, headers=owner["headers"])
    first_id = first.json()["id"]
    assert await _list_status() == "draft"
    assert await _detail_status() == "draft"

    await client.post(f"{base}/{first_id}/approve", headers=owner["headers"])
    assert await _list_status() == "approved"
    assert await _detail_status() == "approved"

    second = await client.post(base, headers=owner["headers"])
    second_id = second.json()["id"]
    assert await _list_status() == "draft"
    assert await _detail_status() == "draft"

    await client.post(f"{base}/{second_id}/reject", headers=owner["headers"])
    assert await _list_status() == "rejected"
    assert await _detail_status() == "rejected"


async def test_strategy_generation_does_not_require_feasibility(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    """Generating a test strategy must work even with zero feasibility
    studies on the requirement - it's never hard-blocked on one existing."""
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])

    resp = await client.post(_strategy_base(project["id"], requirement["id"]), headers=owner["headers"])
    assert resp.status_code == 201, resp.text


async def test_strategy_reflects_approved_feasibility_context(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    """Generating a strategy after an approved feasibility study must
    actually use that study as context - not a no-op. We don't over-specify
    exact wording: we just confirm the strategy's summary changes to
    reference the feasibility study's scenario count once one is approved,
    compared to generating a strategy with no feasibility study at all."""
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])

    # Baseline: strategy generated with no feasibility study on record.
    baseline_resp = await client.post(
        _strategy_base(project["id"], requirement["id"]), headers=owner["headers"]
    )
    assert baseline_resp.status_code == 201
    baseline_summary = baseline_resp.json()["payload"]["summary"]

    # Create and approve a feasibility study.
    feasibility_resp = await client.post(
        _feasibility_base(project["id"], requirement["id"]), headers=owner["headers"]
    )
    assert feasibility_resp.status_code == 201
    feasibility = feasibility_resp.json()
    scenario_count = len(feasibility["payload"]["scenarios"])
    approve_resp = await client.post(
        f"{_feasibility_base(project['id'], requirement['id'])}/{feasibility['id']}/approve",
        headers=owner["headers"],
    )
    assert approve_resp.status_code == 200

    # Generate a second strategy now that an approved feasibility study exists.
    informed_resp = await client.post(
        _strategy_base(project["id"], requirement["id"]), headers=owner["headers"]
    )
    assert informed_resp.status_code == 201
    informed_payload = informed_resp.json()["payload"]

    # The linkage isn't a no-op: the strategy's summary/notes now differ from
    # the no-feasibility baseline, and concretely mention the feasibility
    # study's scenario count somewhere in the summary or scope notes.
    assert informed_payload["summary"] != baseline_summary
    haystack = " ".join(
        [informed_payload["summary"], informed_payload["automation_scope_notes"], informed_payload["manual_scope_notes"]]
    )
    assert str(scenario_count) in haystack


async def test_project_isolation_strategy_unreachable_from_other_project(
    user_a: dict, user_b: dict, client: AsyncClient
) -> None:
    project_b = await _create_project(client, user_b["headers"], "B's project")
    requirement_b = await _create_requirement(client, user_b["headers"], project_b["id"])
    base_b = _strategy_base(project_b["id"], requirement_b["id"])
    created = await client.post(base_b, headers=user_b["headers"])
    strategy_id = created.json()["id"]

    assert (await client.get(base_b, headers=user_a["headers"])).status_code == 404
    assert (await client.get(f"{base_b}/{strategy_id}", headers=user_a["headers"])).status_code == 404
    assert (await client.post(base_b, headers=user_a["headers"])).status_code == 404
    assert (
        await client.patch(
            f"{base_b}/{strategy_id}", json={"payload": created.json()["payload"]}, headers=user_a["headers"]
        )
    ).status_code == 404
    assert (await client.post(f"{base_b}/{strategy_id}/approve", headers=user_a["headers"])).status_code == 404
    assert (await client.post(f"{base_b}/{strategy_id}/reject", headers=user_a["headers"])).status_code == 404
