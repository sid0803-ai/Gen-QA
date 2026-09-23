"""Tests for the reporting domain
(/api/v1/projects/{project_id}/dashboard, /reports/trend, /reports/breakdown,
/requirements/{requirement_id}/coverage).

Every arithmetic assertion here is against exact numbers derived from a
small, fully-known fixture built in each test (never a vague "> 0" check) -
per this sprint's own verification requirement. Executions are created via
the real API (manual, immediately-terminal) and then, where a specific
`completed_at` date is required (the trend endpoint), the just-created row's
`completed_at` is rewritten directly through the shared `db_session` fixture
(same connection the `client` fixture's overridden `get_db` uses, so the
change is visible to the very next request) - not recreated via a slower or
nonexistent "backdated execution" API, which does not exist by design (an
execution records something that already happened *now*, see
`app.domains.executions`'s own docstrings).
"""
import datetime
import uuid
from collections.abc import Awaitable, Callable

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.executions.models import Execution


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


async def _create_requirement(client: AsyncClient, headers: dict, project_id: str, title: str = "Users can log in") -> dict:
    body = {"title": title, "description": "As a user, I want to log in with email/password."}
    resp = await client.post(f"/api/v1/projects/{project_id}/requirements", json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_test_case(
    client: AsyncClient,
    headers: dict,
    project_id: str,
    requirement_id: str,
    *,
    title: str = "Login succeeds with valid credentials",
    testing_level: str = "ui",
    category: str = "positive",
    priority: str = "high",
    execution_type: str | None = None,
    automation_candidate: bool = True,
) -> dict:
    body = {
        "requirement_id": requirement_id,
        "title": title,
        "category": category,
        "testing_level": testing_level,
        "priority": priority,
        "severity": "major",
        "preconditions": "A registered user account exists.",
        "test_data": "Valid email/password pair.",
        "steps": ["Navigate to the login page.", "Enter valid credentials.", "Submit."],
        "expected_result": "The user is logged in.",
        "automation_candidate": automation_candidate,
    }
    resp = await client.post(f"/api/v1/projects/{project_id}/test-cases", json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    test_case = resp.json()

    if execution_type is not None and execution_type != test_case["execution_type"]:
        patch_resp = await client.patch(
            f"/api/v1/projects/{project_id}/test-cases/{test_case['id']}",
            json={"execution_type": execution_type},
            headers=headers,
        )
        assert patch_resp.status_code == 200, patch_resp.text
        test_case = patch_resp.json()
    return test_case


async def _create_environment(client: AsyncClient, headers: dict, project_id: str, base_url: str = "https://staging.example.com") -> dict:
    resp = await client.post(
        f"/api/v1/projects/{project_id}/environments",
        json={"name": "Staging", "base_url": base_url},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _approve_automation_script(client: AsyncClient, headers: dict, project_id: str, test_case_id: str, environment_id: str) -> None:
    gen_resp = await client.post(
        f"/api/v1/projects/{project_id}/test-cases/{test_case_id}/automation-script",
        json={"environment_id": environment_id},
        headers=headers,
    )
    assert gen_resp.status_code == 201, gen_resp.text
    approve_resp = await client.post(
        f"/api/v1/projects/{project_id}/test-cases/{test_case_id}/automation-script/approve",
        headers=headers,
    )
    assert approve_resp.status_code == 200, approve_resp.text


async def _record_manual_execution(
    client: AsyncClient, headers: dict, project_id: str, test_case_id: str, environment_id: str, status: str
) -> dict:
    resp = await client.post(
        f"/api/v1/projects/{project_id}/executions",
        json={
            "test_case_id": test_case_id,
            "environment_id": environment_id,
            "type": "manual",
            "status": status,
            "actual_result": f"Recorded as {status}.",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _set_completed_at(db_session: AsyncSession, execution_id: str, when: datetime.datetime) -> None:
    result = await db_session.execute(select(Execution).where(Execution.id == uuid.UUID(execution_id)))
    execution = result.scalar_one()
    execution.completed_at = when
    execution.started_at = when
    await db_session.commit()


def _dashboard_url(project_id: str) -> str:
    return f"/api/v1/projects/{project_id}/dashboard"


def _trend_url(project_id: str, days: int | None = None) -> str:
    base = f"/api/v1/projects/{project_id}/reports/trend"
    return f"{base}?days={days}" if days is not None else base


def _breakdown_url(project_id: str) -> str:
    return f"/api/v1/projects/{project_id}/reports/breakdown"


def _coverage_url(project_id: str, requirement_id: str) -> str:
    return f"/api/v1/projects/{project_id}/requirements/{requirement_id}/coverage"


# --- Dashboard --------------------------------------------------------------


async def test_dashboard_exact_arithmetic(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    environment = await _create_environment(client, owner["headers"], project["id"])
    headers = owner["headers"]
    pid = project["id"]

    # TC1: has an approved automation script, latest execution "passed"
    # (created after an earlier "failed" one, to prove "latest" means
    # highest `sequence`, not merely "any" execution).
    tc1 = await _create_test_case(client, headers, pid, requirement["id"], title="TC1")
    await _approve_automation_script(client, headers, pid, tc1["id"], environment["id"])
    await _record_manual_execution(client, headers, pid, tc1["id"], environment["id"], "failed")
    await _record_manual_execution(client, headers, pid, tc1["id"], environment["id"], "passed")

    # TC2: no automation script, latest execution "passed".
    tc2 = await _create_test_case(client, headers, pid, requirement["id"], title="TC2", automation_candidate=False)
    await _record_manual_execution(client, headers, pid, tc2["id"], environment["id"], "passed")

    # TC3: no automation script, latest execution "failed".
    tc3 = await _create_test_case(client, headers, pid, requirement["id"], title="TC3", automation_candidate=False)
    await _record_manual_execution(client, headers, pid, tc3["id"], environment["id"], "blocked")
    await _record_manual_execution(client, headers, pid, tc3["id"], environment["id"], "failed")

    # TC4: no executions at all -> "none".
    tc4 = await _create_test_case(client, headers, pid, requirement["id"], title="TC4", automation_candidate=False)

    resp = await client.get(_dashboard_url(pid), headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["requirements_count"] == 1
    assert body["test_cases_count"] == 4
    assert body["automation_candidate_count"] == 1
    assert body["automation_coverage_pct"] == pytest.approx(25.0)
    assert body["executions_total"] == 5
    assert body["in_progress_count"] == 0
    assert body["latest_status_breakdown"] == {
        "passed": 2,
        "failed": 1,
        "blocked": 0,
        "skipped": 0,
        "error": 0,
        "none": 1,
    }
    # Terminal latest statuses: 2 passed + 1 failed = 3 -> pass rate 2/3,
    # rounded to 2 decimal places by the endpoint.
    assert body["pass_rate_pct"] == round(2 / 3 * 100, 2)
    assert body["open_failures_count"] == 1
    assert body["scheduled_jobs_count"] == 0
    assert set(tc4) == set(tc4)  # tc4 kept only to document the "none" case above


async def test_dashboard_zero_test_cases_has_null_pass_rate_and_zero_coverage(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])

    resp = await client.get(_dashboard_url(project["id"]), headers=owner["headers"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["requirements_count"] == 0
    assert body["test_cases_count"] == 0
    assert body["automation_candidate_count"] == 0
    assert body["automation_coverage_pct"] == 0.0
    assert body["pass_rate_pct"] is None
    assert body["latest_status_breakdown"] == {
        "passed": 0, "failed": 0, "blocked": 0, "skipped": 0, "error": 0, "none": 0,
    }


async def test_dashboard_non_member_gets_404(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    outsider = await register_user()
    project = await _create_project(client, owner["headers"])

    resp = await client.get(_dashboard_url(project["id"]), headers=outsider["headers"])
    assert resp.status_code == 404, resp.text


# --- Trend --------------------------------------------------------------


async def test_trend_zero_filled_and_grouped_by_completion_date(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient, db_session: AsyncSession
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    environment = await _create_environment(client, owner["headers"], project["id"])
    headers = owner["headers"]
    pid = project["id"]
    tc = await _create_test_case(client, headers, pid, requirement["id"], automation_candidate=False)

    today = datetime.datetime.now(datetime.timezone.utc)
    two_days_ago = today - datetime.timedelta(days=2)

    exec_today_pass = await _record_manual_execution(client, headers, pid, tc["id"], environment["id"], "passed")
    exec_today_fail = await _record_manual_execution(client, headers, pid, tc["id"], environment["id"], "failed")
    exec_2d_ago = await _record_manual_execution(client, headers, pid, tc["id"], environment["id"], "blocked")

    await _set_completed_at(db_session, exec_today_pass["id"], today)
    await _set_completed_at(db_session, exec_today_fail["id"], today)
    await _set_completed_at(db_session, exec_2d_ago["id"], two_days_ago)

    resp = await client.get(_trend_url(pid, days=5), headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert len(body) == 5
    dates = [p["date"] for p in body]
    assert dates == sorted(dates)  # oldest to newest
    assert dates[-1] == today.date().isoformat()
    assert dates[-3] == two_days_ago.date().isoformat()

    today_point = body[-1]
    assert today_point["passed"] == 1
    assert today_point["failed"] == 1
    assert today_point["blocked"] == 0
    assert today_point["skipped"] == 0
    assert today_point["error"] == 0
    assert today_point["total"] == 2

    two_days_ago_point = body[-3]
    assert two_days_ago_point["blocked"] == 1
    assert two_days_ago_point["total"] == 1

    # Every other day is zero-filled.
    for i, point in enumerate(body):
        if i in (len(body) - 1, len(body) - 3):
            continue
        assert point["total"] == 0
        assert point == {
            "date": point["date"], "passed": 0, "failed": 0, "blocked": 0, "skipped": 0, "error": 0, "total": 0,
        }


async def test_trend_default_days_is_30_and_validates_range(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])

    resp = await client.get(_trend_url(project["id"]), headers=owner["headers"])
    assert resp.status_code == 200, resp.text
    assert len(resp.json()) == 30

    too_small = await client.get(_trend_url(project["id"], days=0), headers=owner["headers"])
    assert too_small.status_code == 422

    too_large = await client.get(_trend_url(project["id"], days=366), headers=owner["headers"])
    assert too_large.status_code == 422


# --- Breakdown --------------------------------------------------------------


async def test_breakdown_by_dimensions_exact_counts(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    environment = await _create_environment(client, owner["headers"], project["id"])
    headers = owner["headers"]
    pid = project["id"]

    tc1 = await _create_test_case(
        client, headers, pid, requirement["id"], title="TC1",
        testing_level="ui", category="positive", priority="high", automation_candidate=False,
    )
    await _record_manual_execution(client, headers, pid, tc1["id"], environment["id"], "passed")

    tc2 = await _create_test_case(
        client, headers, pid, requirement["id"], title="TC2",
        testing_level="ui", category="negative", priority="high", automation_candidate=False,
    )
    await _record_manual_execution(client, headers, pid, tc2["id"], environment["id"], "failed")

    tc3 = await _create_test_case(
        client, headers, pid, requirement["id"], title="TC3",
        testing_level="api", category="positive", priority="low", automation_candidate=False,
    )
    # no executions -> no_runs

    resp = await client.get(_breakdown_url(pid), headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    by_level = {row["testing_level"]: row for row in body["by_testing_level"]}
    assert by_level["ui"]["total"] == 2
    assert by_level["ui"]["passed"] == 1
    assert by_level["ui"]["failed"] == 1
    assert by_level["ui"]["no_runs"] == 0
    assert by_level["api"]["total"] == 1
    assert by_level["api"]["no_runs"] == 1
    # No other testing levels appear (empty buckets are skipped).
    assert set(by_level.keys()) == {"ui", "api"}

    by_category = {row["category"]: row for row in body["by_category"]}
    assert by_category["positive"]["total"] == 2
    assert by_category["positive"]["passed"] == 1
    assert by_category["positive"]["no_runs"] == 1
    assert by_category["negative"]["total"] == 1
    assert by_category["negative"]["failed"] == 1
    assert set(by_category.keys()) == {"positive", "negative"}

    by_priority = {row["priority"]: row for row in body["by_priority"]}
    assert by_priority["high"]["total"] == 2
    assert by_priority["low"]["total"] == 1
    assert set(by_priority.keys()) == {"high", "low"}


# --- Requirement coverage ----------------------------------------------------


async def test_requirement_coverage_exact_counts(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])
    other_requirement = await _create_requirement(client, owner["headers"], project["id"], title="Other req")
    environment = await _create_environment(client, owner["headers"], project["id"])
    headers = owner["headers"]
    pid = project["id"]

    tc1 = await _create_test_case(
        client, headers, pid, requirement["id"], title="TC1", execution_type="automation", automation_candidate=True,
    )
    await _approve_automation_script(client, headers, pid, tc1["id"], environment["id"])
    await _record_manual_execution(client, headers, pid, tc1["id"], environment["id"], "passed")

    tc2 = await _create_test_case(
        client, headers, pid, requirement["id"], title="TC2", execution_type="manual", automation_candidate=False,
    )
    await _record_manual_execution(client, headers, pid, tc2["id"], environment["id"], "failed")

    tc3 = await _create_test_case(
        client, headers, pid, requirement["id"], title="TC3", execution_type="hybrid", automation_candidate=False,
    )
    # no executions

    # A test case on a DIFFERENT requirement must not be counted.
    other_tc = await _create_test_case(
        client, headers, pid, other_requirement["id"], title="Other TC", automation_candidate=False,
    )
    await _record_manual_execution(client, headers, pid, other_tc["id"], environment["id"], "passed")

    resp = await client.get(_coverage_url(pid, requirement["id"]), headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["requirement_id"] == requirement["id"]
    assert body["test_case_count"] == 3
    assert body["automated_count"] == 1
    assert body["manual_count"] == 1
    assert body["hybrid_count"] == 1
    assert body["automation_script_approved_count"] == 1
    assert body["latest_status_breakdown"] == {
        "passed": 1, "failed": 1, "blocked": 0, "skipped": 0, "error": 0, "none": 1,
    }
    assert body["pass_rate_pct"] == pytest.approx(1 / 2 * 100, rel=1e-6)


async def test_requirement_coverage_404_for_requirement_not_in_project(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project_a = await _create_project(client, owner["headers"], name="A")
    project_b = await _create_project(client, owner["headers"], name="B")
    requirement_b = await _create_requirement(client, owner["headers"], project_b["id"])

    resp = await client.get(_coverage_url(project_a["id"], requirement_b["id"]), headers=owner["headers"])
    assert resp.status_code == 404, resp.text


async def test_requirement_coverage_zero_test_cases_has_null_pass_rate(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    requirement = await _create_requirement(client, owner["headers"], project["id"])

    resp = await client.get(_coverage_url(project["id"], requirement["id"]), headers=owner["headers"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["test_case_count"] == 0
    assert body["pass_rate_pct"] is None
