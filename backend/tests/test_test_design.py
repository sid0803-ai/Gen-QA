"""Tests for
/api/v1/projects/{project_id}/requirements/{requirement_id}/test-design/*:
mock test-design generation, `scope` biasing testing_level, edit-while-draft
(toggling `include`), approve/reject lifecycle - including verifying that
approval promotes every `include == true` scenario into a permanent
TestCase row (and that `include == false` scenarios are NOT promoted), role
enforcement, latest_test_design_status on the requirement list/detail
endpoints, and that generating a design after an approved test strategy
actually uses that context. Mirrors test_strategy.py's structure."""
from collections.abc import Awaitable, Callable

from httpx import AsyncClient

PAYLOAD_KEYS = {"summary", "scope", "scenarios"}
SCENARIO_KEYS = {
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
    "include",
}
VALID_CATEGORIES = {
    "positive",
    "negative",
    "boundary",
    "edge_case",
    "business_logic",
    "validation",
    "security",
    "performance",
    "regression",
}
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
        "third-party payment gateway integration, protected by a CAPTCHA, so that I don't "
        "have to mail a check."
    ),
    **extra,
) -> dict:
    body = {"title": title, "description": description, **extra}
    resp = await client.post(
        f"/api/v1/projects/{project_id}/requirements", json=body, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _design_base(project_id: str, requirement_id: str) -> str:
    return f"/api/v1/projects/{project_id}/requirements/{requirement_id}/test-design"


def _strategy_base(project_id: str, requirement_id: str) -> str:
    return f"/api/v1/projects/{project_id}/requirements/{requirement_id}/strategy"


def _test_cases_base(project_id: str) -> str:
    return f"/api/v1/projects/{project_id}/test-cases"


async def _create_test_design(
    client: AsyncClient, headers: dict, project_id: str, requirement_id: str, scope: str = "both"
):
    resp = await client.post(
        _design_base(project_id, requirement_id), json={"scope": scope}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_trigger_test_design_creates_draft_with_full_payload(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])

    design = await _create_test_design(client, owner["headers"], project["id"], requirement["id"], scope="both")

    assert design["requirement_id"] == requirement["id"]
    assert design["status"] == "draft"
    assert design["created_by"] == owner["user"]["id"]
    assert design["approved_by"] is None
    assert design["approved_at"] is None

    payload = design["payload"]
    assert set(payload.keys()) == PAYLOAD_KEYS
    assert payload["summary"]
    assert payload["scope"] == "both"
    assert 4 <= len(payload["scenarios"]) <= 10

    categories_seen = set()
    for scenario in payload["scenarios"]:
        assert set(scenario.keys()) == SCENARIO_KEYS
        assert scenario["title"]
        assert scenario["category"] in VALID_CATEGORIES
        assert scenario["testing_level"] in VALID_LEVELS
        assert scenario["priority"] in ("low", "medium", "high", "critical")
        assert scenario["severity"] in ("minor", "major", "critical", "blocker")
        assert isinstance(scenario["steps"], list) and len(scenario["steps"]) >= 1
        assert scenario["expected_result"]
        assert isinstance(scenario["automation_candidate"], bool)
        # AI proposes every scenario for promotion by default.
        assert scenario["include"] is True
        categories_seen.add(scenario["category"])

    # Never all-positive: at least one negative and one boundary/edge_case
    # scenario must be present, per this sprint's spec.
    assert "positive" in categories_seen
    assert "negative" in categories_seen
    assert "boundary" in categories_seen or "edge_case" in categories_seen
    # This requirement's text mentions CAPTCHA and a payment gateway -> the
    # mock provider should surface at least one non-automation-candidate
    # scenario (content varies with input).
    assert any(not s["automation_candidate"] for s in payload["scenarios"])


async def test_scope_biases_testing_level_distribution(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])

    api_design = await _create_test_design(client, owner["headers"], project["id"], requirement["id"], scope="api")
    api_levels = {s["testing_level"] for s in api_design["payload"]["scenarios"]}
    assert "ui" not in api_levels

    ui_design = await _create_test_design(client, owner["headers"], project["id"], requirement["id"], scope="ui")
    ui_levels = {s["testing_level"] for s in ui_design["payload"]["scenarios"]}
    assert "api" not in ui_levels
    assert "integration" not in ui_levels


async def test_trigger_test_design_role_enforcement(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    viewer = await register_user()
    await _add_member(client, owner["headers"], project["id"], viewer["email"], "viewer")
    stranger = await register_user()

    viewer_resp = await client.post(
        _design_base(project["id"], requirement["id"]), json={"scope": "both"}, headers=viewer["headers"]
    )
    assert viewer_resp.status_code == 403

    stranger_resp = await client.post(
        _design_base(project["id"], requirement["id"]), json={"scope": "both"}, headers=stranger["headers"]
    )
    assert stranger_resp.status_code == 404


async def test_list_and_get_test_designs(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])

    created = await _create_test_design(client, owner["headers"], project["id"], requirement["id"])
    design_id = created["id"]
    base = _design_base(project["id"], requirement["id"])

    listing = await client.get(base, headers=owner["headers"])
    assert listing.status_code == 200
    items = listing.json()
    assert len(items) == 1
    assert "payload" not in items[0]

    detail = await client.get(f"{base}/{design_id}", headers=owner["headers"])
    assert detail.status_code == 200
    assert "payload" in detail.json()

    viewer = await register_user()
    await _add_member(client, owner["headers"], project["id"], viewer["email"], "viewer")
    viewer_list = await client.get(base, headers=viewer["headers"])
    assert viewer_list.status_code == 200


async def test_get_test_design_nonexistent_returns_404(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])

    resp = await client.get(
        f"{_design_base(project['id'], requirement['id'])}/00000000-0000-0000-0000-000000000000",
        headers=owner["headers"],
    )
    assert resp.status_code == 404


async def test_approve_lifecycle_promotes_included_scenarios_to_test_cases(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])

    created = await _create_test_design(client, owner["headers"], project["id"], requirement["id"])
    design_id = created["id"]
    base = _design_base(project["id"], requirement["id"])

    # Human edits the draft: excludes the first scenario from promotion,
    # edits the second scenario's title (proving PATCH-while-draft applies).
    payload = dict(created["payload"])
    scenarios = [dict(s) for s in payload["scenarios"]]
    excluded_title = scenarios[0]["title"]
    scenarios[0]["include"] = False
    scenarios[1]["title"] = "Edited by human reviewer"
    payload["scenarios"] = scenarios

    edit_resp = await client.patch(f"{base}/{design_id}", json={"payload": payload}, headers=owner["headers"])
    assert edit_resp.status_code == 200
    edited = edit_resp.json()
    assert edited["status"] == "draft"
    assert edited["payload"]["scenarios"][0]["include"] is False
    assert edited["payload"]["scenarios"][1]["title"] == "Edited by human reviewer"

    included_scenarios = [s for s in edited["payload"]["scenarios"] if s["include"]]

    approve_resp = await client.post(f"{base}/{design_id}/approve", headers=owner["headers"])
    assert approve_resp.status_code == 200
    approved = approve_resp.json()
    assert approved["status"] == "approved"
    assert approved["approved_by"] == owner["user"]["id"]
    assert approved["approved_at"] is not None
    assert approved["created_test_case_count"] == len(included_scenarios)
    assert len(approved["created_test_case_ids"]) == len(included_scenarios)

    # Editing/approving/rejecting an already-approved test design is no
    # longer allowed.
    assert (
        await client.patch(f"{base}/{design_id}", json={"payload": payload}, headers=owner["headers"])
    ).status_code == 409
    assert (await client.post(f"{base}/{design_id}/approve", headers=owner["headers"])).status_code == 409
    assert (await client.post(f"{base}/{design_id}/reject", headers=owner["headers"])).status_code == 409

    # Verify the promoted TestCase rows exist, with correct data, and that
    # the excluded scenario was NOT promoted.
    listing = await client.get(
        f"{_test_cases_base(project['id'])}?requirement_id={requirement['id']}", headers=owner["headers"]
    )
    assert listing.status_code == 200
    test_case_rows = listing.json()
    assert len(test_case_rows) == len(included_scenarios)

    promoted_titles = {row["title"] for row in test_case_rows}
    assert excluded_title not in promoted_titles
    assert "Edited by human reviewer" in promoted_titles
    assert {row["id"] for row in test_case_rows} == set(approved["created_test_case_ids"])

    for row in test_case_rows:
        assert row["source"] == "ai"
        assert row["status"] == "approved"
        assert row["requirement_id"] == requirement["id"]
        assert row["requirement_title"] == requirement["title"]
        assert row["code"].startswith("TC-")

    edited_scenario = next(s for s in included_scenarios if s["title"] == "Edited by human reviewer")
    detail_resp = await client.get(
        f"{_test_cases_base(project['id'])}/{next(r['id'] for r in test_case_rows if r['title'] == 'Edited by human reviewer')}",
        headers=owner["headers"],
    )
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["category"] == edited_scenario["category"]
    assert detail["testing_level"] == edited_scenario["testing_level"]
    assert detail["priority"] == edited_scenario["priority"]
    assert detail["severity"] == edited_scenario["severity"]
    assert detail["preconditions"] == edited_scenario["preconditions"]
    assert detail["test_data"] == edited_scenario["test_data"]
    assert detail["steps"] == edited_scenario["steps"]
    assert detail["expected_result"] == edited_scenario["expected_result"]
    assert detail["business_rule"] == edited_scenario["business_rule"]
    assert detail["automation_candidate"] == edited_scenario["automation_candidate"]
    assert detail["test_design_id"] == design_id


async def test_reject_lifecycle_creates_no_test_cases(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])

    created = await _create_test_design(client, owner["headers"], project["id"], requirement["id"])
    design_id = created["id"]
    base = _design_base(project["id"], requirement["id"])

    reject_resp = await client.post(f"{base}/{design_id}/reject", headers=owner["headers"])
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "rejected"

    edit_again = await client.patch(
        f"{base}/{design_id}", json={"payload": created["payload"]}, headers=owner["headers"]
    )
    assert edit_again.status_code == 409
    assert (await client.post(f"{base}/{design_id}/reject", headers=owner["headers"])).status_code == 409
    assert (await client.post(f"{base}/{design_id}/approve", headers=owner["headers"])).status_code == 409

    listing = await client.get(
        f"{_test_cases_base(project['id'])}?requirement_id={requirement['id']}", headers=owner["headers"]
    )
    assert listing.status_code == 200
    assert listing.json() == []


async def test_test_design_write_actions_require_member_role(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    viewer = await register_user()
    await _add_member(client, owner["headers"], project["id"], viewer["email"], "viewer")

    created = await _create_test_design(client, owner["headers"], project["id"], requirement["id"])
    base = _design_base(project["id"], requirement["id"])

    edit_resp = await client.patch(
        f"{base}/{created['id']}", json={"payload": created["payload"]}, headers=viewer["headers"]
    )
    assert edit_resp.status_code == 403
    assert (await client.post(f"{base}/{created['id']}/approve", headers=viewer["headers"])).status_code == 403
    assert (await client.post(f"{base}/{created['id']}/reject", headers=viewer["headers"])).status_code == 403


async def test_second_test_design_does_not_affect_first(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    base = _design_base(project["id"], requirement["id"])

    first = await _create_test_design(client, owner["headers"], project["id"], requirement["id"])
    first_id = first["id"]

    await client.post(f"{base}/{first_id}/approve", headers=owner["headers"])

    second = await _create_test_design(client, owner["headers"], project["id"], requirement["id"])
    assert second["status"] == "draft"
    assert second["id"] != first_id

    first_detail = await client.get(f"{base}/{first_id}", headers=owner["headers"])
    assert first_detail.json()["status"] == "approved"

    listing = await client.get(base, headers=owner["headers"])
    items = listing.json()
    assert len(items) == 2
    assert items[0]["id"] == second["id"]
    assert items[1]["id"] == first_id


async def test_latest_test_design_status_reflects_most_recent(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    base = _design_base(project["id"], requirement["id"])

    def _latest_status_in_list(items: list[dict], requirement_id: str) -> str:
        matches = [i for i in items if i["id"] == requirement_id]
        assert len(matches) == 1
        return matches[0]["latest_test_design_status"]

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
        return resp.json()["latest_test_design_status"]

    assert await _list_status() == "none"
    assert await _detail_status() == "none"

    first = await _create_test_design(client, owner["headers"], project["id"], requirement["id"])
    assert await _list_status() == "draft"
    assert await _detail_status() == "draft"

    await client.post(f"{base}/{first['id']}/approve", headers=owner["headers"])
    assert await _list_status() == "approved"
    assert await _detail_status() == "approved"

    second = await _create_test_design(client, owner["headers"], project["id"], requirement["id"])
    assert await _list_status() == "draft"
    assert await _detail_status() == "draft"

    await client.post(f"{base}/{second['id']}/reject", headers=owner["headers"])
    assert await _list_status() == "rejected"
    assert await _detail_status() == "rejected"


async def test_test_design_generation_does_not_require_strategy(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    """Generating a test design must work even with zero approved test
    strategies on the requirement - it's never hard-blocked on one
    existing."""
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])

    design = await _create_test_design(client, owner["headers"], project["id"], requirement["id"])
    assert design["status"] == "draft"


async def test_test_design_reflects_approved_strategy_context(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    """Generating a design after an approved test strategy must actually
    use that strategy as context - not a no-op."""
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])

    baseline = await _create_test_design(client, owner["headers"], project["id"], requirement["id"], scope="both")
    baseline_summary = baseline["payload"]["summary"]

    strategy_resp = await client.post(
        _strategy_base(project["id"], requirement["id"]), headers=owner["headers"]
    )
    assert strategy_resp.status_code == 201
    strategy = strategy_resp.json()
    approve_resp = await client.post(
        f"{_strategy_base(project['id'], requirement['id'])}/{strategy['id']}/approve",
        headers=owner["headers"],
    )
    assert approve_resp.status_code == 200

    informed = await _create_test_design(client, owner["headers"], project["id"], requirement["id"], scope="both")
    assert informed["payload"]["summary"] != baseline_summary
    assert "test strategy" in informed["payload"]["summary"].lower()


async def test_project_isolation_test_design_unreachable_from_other_project(
    user_a: dict, user_b: dict, client: AsyncClient
) -> None:
    project_b = await _create_project(client, user_b["headers"], "B's project")
    requirement_b = await _create_requirement(client, user_b["headers"], project_b["id"])
    base_b = _design_base(project_b["id"], requirement_b["id"])
    created = await _create_test_design(client, user_b["headers"], project_b["id"], requirement_b["id"])
    design_id = created["id"]

    assert (await client.get(base_b, headers=user_a["headers"])).status_code == 404
    assert (await client.get(f"{base_b}/{design_id}", headers=user_a["headers"])).status_code == 404
    assert (
        await client.post(base_b, json={"scope": "both"}, headers=user_a["headers"])
    ).status_code == 404
    assert (
        await client.patch(
            f"{base_b}/{design_id}", json={"payload": created["payload"]}, headers=user_a["headers"]
        )
    ).status_code == 404
    assert (await client.post(f"{base_b}/{design_id}/approve", headers=user_a["headers"])).status_code == 404
    assert (await client.post(f"{base_b}/{design_id}/reject", headers=user_a["headers"])).status_code == 404
