"""Tests for /api/v1/projects/{project_id}/performance-tests/* (performance
domain): CRUD, role enforcement, project isolation, vus/duration validation
bounds, k6-summary-parsing correctness, and k6-not-found graceful failure.

No real k6 binary is available in this environment, so the actual k6
subprocess call (`app.domains.performance.service.run_k6_script`) is
monkeypatched in the two end-to-end "trigger a run" tests below - the rest
of the pipeline (task lookup, substitution resolution, DB writes) is real.

The end-to-end run tests deliberately do NOT use the shared `client`/
`db_session` fixture. Celery's `task_always_eager` mode (set globally in
conftest.py) runs `run_performance_test` inline, but that task (see
`app.domains.performance.tasks._run()`) opens its OWN dedicated DB engine to
look up the run/test/saved request - a genuinely separate Postgres
connection that cannot see rows created through the shared fixture's single
connection/SAVEPOINT-wrapped, never-truly-committed transaction. So these
two tests use their own independent engine/sessions with real commits
instead - the same pattern `tests/test_executions.py`'s own end-to-end
automated-execution tests already established for exactly this problem.
"""
import os
import uuid as uuid_lib

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.domains.api_performer.models import ApiCollection, HttpMethod, SavedApiRequest
from app.domains.identity.models import User
from app.domains.performance import repository as performance_repository
from app.domains.performance import service as performance_service
from app.domains.performance.models import PerformanceTest, PerformanceTestRunStatus
from app.domains.projects.models import Project, ProjectMember, ProjectRole

READ_KEYS = {
    "id",
    "project_id",
    "saved_request_id",
    "name",
    "vus",
    "duration_seconds",
    "created_by",
    "created_at",
    "updated_at",
}

RUN_SUMMARY_KEYS = {
    "id",
    "performance_test_id",
    "status",
    "vus",
    "duration_seconds",
    "started_at",
    "completed_at",
    "request_count",
    "failed_count",
    "error_rate",
    "avg_duration_ms",
    "p95_duration_ms",
    "min_duration_ms",
    "max_duration_ms",
    "requests_per_second",
    "error_message",
    "created_by",
}


# --- Shared-fixture helpers ------------------------------------------------


async def _create_project(client: AsyncClient, headers: dict, name: str = "Perf Project") -> dict:
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


async def _create_collection(client: AsyncClient, headers: dict, project_id: str) -> dict:
    resp = await client.post(
        f"/api/v1/projects/{project_id}/api-collections", json={"name": "Collection"}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_saved_request(client: AsyncClient, headers: dict, project_id: str, **overrides) -> dict:
    if "collection_id" not in overrides:
        collection = await _create_collection(client, headers, project_id)
        overrides = {**overrides, "collection_id": collection["id"]}
    body = {"name": "Ping", "method": "GET", "url": "https://example.com/ping"}
    body.update(overrides)
    resp = await client.post(f"/api/v1/projects/{project_id}/api-requests", json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _base(project_id: str) -> str:
    return f"/api/v1/projects/{project_id}/performance-tests"


async def _create_performance_test(
    client: AsyncClient, headers: dict, project_id: str, saved_request_id: str, **overrides
) -> dict:
    body = {"saved_request_id": saved_request_id, "name": "Load Test", "vus": 5, "duration_seconds": 10}
    body.update(overrides)
    resp = await client.post(_base(project_id), json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- CRUD ------------------------------------------------------------------


async def test_create_and_get_performance_test(user_a: dict, client: AsyncClient) -> None:
    project = await _create_project(client, user_a["headers"])
    saved_request = await _create_saved_request(client, user_a["headers"], project["id"])

    created = await _create_performance_test(
        client, user_a["headers"], project["id"], saved_request["id"]
    )
    assert set(created.keys()) == READ_KEYS
    assert created["name"] == "Load Test"
    assert created["vus"] == 5
    assert created["duration_seconds"] == 10
    assert created["saved_request_id"] == saved_request["id"]

    resp = await client.get(f"{_base(project['id'])}/{created['id']}", headers=user_a["headers"])
    assert resp.status_code == 200, resp.text
    assert resp.json() == created


async def test_create_defaults_vus_and_duration(user_a: dict, client: AsyncClient) -> None:
    project = await _create_project(client, user_a["headers"])
    saved_request = await _create_saved_request(client, user_a["headers"], project["id"])

    resp = await client.post(
        _base(project["id"]),
        json={"saved_request_id": saved_request["id"], "name": "Defaults"},
        headers=user_a["headers"],
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["vus"] == 5
    assert body["duration_seconds"] == 30


async def test_create_with_unknown_saved_request_returns_404(user_a: dict, client: AsyncClient) -> None:
    project = await _create_project(client, user_a["headers"])
    resp = await client.post(
        _base(project["id"]),
        json={"saved_request_id": str(uuid_lib.uuid4()), "name": "X"},
        headers=user_a["headers"],
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.parametrize(
    "field,value",
    [
        ("vus", 0),
        ("vus", 501),
        ("duration_seconds", 0),
        ("duration_seconds", 3601),
    ],
)
async def test_create_rejects_out_of_bounds_vus_and_duration(
    user_a: dict, client: AsyncClient, field: str, value: int
) -> None:
    project = await _create_project(client, user_a["headers"])
    saved_request = await _create_saved_request(client, user_a["headers"], project["id"])
    body = {"saved_request_id": saved_request["id"], "name": "Bounds", field: value}
    resp = await client.post(_base(project["id"]), json=body, headers=user_a["headers"])
    assert resp.status_code == 422, resp.text


async def test_list_performance_tests_ordered_newest_first(user_a: dict, client: AsyncClient) -> None:
    project = await _create_project(client, user_a["headers"])
    saved_request = await _create_saved_request(client, user_a["headers"], project["id"])
    first = await _create_performance_test(client, user_a["headers"], project["id"], saved_request["id"], name="First")
    second = await _create_performance_test(client, user_a["headers"], project["id"], saved_request["id"], name="Second")

    resp = await client.get(_base(project["id"]), headers=user_a["headers"])
    assert resp.status_code == 200, resp.text
    ids = [t["id"] for t in resp.json()]
    assert ids.index(second["id"]) < ids.index(first["id"])


async def test_update_performance_test_partial(user_a: dict, client: AsyncClient) -> None:
    project = await _create_project(client, user_a["headers"])
    saved_request = await _create_saved_request(client, user_a["headers"], project["id"])
    created = await _create_performance_test(client, user_a["headers"], project["id"], saved_request["id"])

    resp = await client.patch(
        f"{_base(project['id'])}/{created['id']}", json={"vus": 20}, headers=user_a["headers"]
    )
    assert resp.status_code == 200, resp.text
    updated = resp.json()
    assert updated["vus"] == 20
    assert updated["name"] == created["name"]
    assert updated["duration_seconds"] == created["duration_seconds"]


async def test_update_rejects_out_of_bounds(user_a: dict, client: AsyncClient) -> None:
    project = await _create_project(client, user_a["headers"])
    saved_request = await _create_saved_request(client, user_a["headers"], project["id"])
    created = await _create_performance_test(client, user_a["headers"], project["id"], saved_request["id"])

    resp = await client.patch(
        f"{_base(project['id'])}/{created['id']}", json={"duration_seconds": 5000}, headers=user_a["headers"]
    )
    assert resp.status_code == 422, resp.text


async def test_delete_performance_test(user_a: dict, client: AsyncClient) -> None:
    project = await _create_project(client, user_a["headers"])
    saved_request = await _create_saved_request(client, user_a["headers"], project["id"])
    created = await _create_performance_test(client, user_a["headers"], project["id"], saved_request["id"])

    resp = await client.delete(f"{_base(project['id'])}/{created['id']}", headers=user_a["headers"])
    assert resp.status_code == 204, resp.text

    resp = await client.get(f"{_base(project['id'])}/{created['id']}", headers=user_a["headers"])
    assert resp.status_code == 404, resp.text


async def test_get_update_delete_unknown_returns_404(user_a: dict, client: AsyncClient) -> None:
    project = await _create_project(client, user_a["headers"])
    fake_id = str(uuid_lib.uuid4())

    resp = await client.get(f"{_base(project['id'])}/{fake_id}", headers=user_a["headers"])
    assert resp.status_code == 404

    resp = await client.patch(f"{_base(project['id'])}/{fake_id}", json={"name": "X"}, headers=user_a["headers"])
    assert resp.status_code == 404

    resp = await client.delete(f"{_base(project['id'])}/{fake_id}", headers=user_a["headers"])
    assert resp.status_code == 404


# --- Role enforcement --------------------------------------------------


async def test_role_enforcement(user_a: dict, user_b: dict, client: AsyncClient) -> None:
    project = await _create_project(client, user_a["headers"])
    saved_request = await _create_saved_request(client, user_a["headers"], project["id"])
    created = await _create_performance_test(client, user_a["headers"], project["id"], saved_request["id"])

    await _add_member(client, user_a["headers"], project["id"], user_b["email"], "viewer")

    # Viewer can read.
    resp = await client.get(_base(project["id"]), headers=user_b["headers"])
    assert resp.status_code == 200, resp.text

    # Viewer cannot create/update/delete/trigger a run.
    resp = await client.post(
        _base(project["id"]),
        json={"saved_request_id": saved_request["id"], "name": "X"},
        headers=user_b["headers"],
    )
    assert resp.status_code == 403, resp.text

    resp = await client.patch(
        f"{_base(project['id'])}/{created['id']}", json={"name": "X"}, headers=user_b["headers"]
    )
    assert resp.status_code == 403, resp.text

    resp = await client.post(f"{_base(project['id'])}/{created['id']}/runs", headers=user_b["headers"])
    assert resp.status_code == 403, resp.text

    resp = await client.delete(f"{_base(project['id'])}/{created['id']}", headers=user_b["headers"])
    assert resp.status_code == 403, resp.text


async def test_project_isolation(user_a: dict, user_b: dict, client: AsyncClient) -> None:
    project_a = await _create_project(client, user_a["headers"], name="Project A")
    saved_request = await _create_saved_request(client, user_a["headers"], project_a["id"])
    created = await _create_performance_test(client, user_a["headers"], project_a["id"], saved_request["id"])

    project_b = await _create_project(client, user_b["headers"], name="Project B")

    # user_b isn't a member of project_a at all -> 404, never 403.
    resp = await client.get(f"{_base(project_a['id'])}/{created['id']}", headers=user_b["headers"])
    assert resp.status_code == 404, resp.text

    resp = await client.get(_base(project_a["id"]), headers=user_b["headers"])
    assert resp.status_code == 404, resp.text

    # Trying to reach project_a's performance test through project_b's URL
    # namespace also 404s (the test row isn't scoped to project_b).
    resp = await client.get(f"{_base(project_b['id'])}/{created['id']}", headers=user_a["headers"])
    assert resp.status_code == 404, resp.text


# --- k6 script generation / summary parsing (pure unit tests) ------------


def test_build_k6_script_embeds_values_safely_via_json_dumps() -> None:
    script = performance_service.build_k6_script(
        method=HttpMethod.POST,
        url="https://example.com/api?x=1&y=\"quote\"",
        headers={"Authorization": "Bearer abc\"; DROP TABLE x;--"},
        body='{"key": "va\'lue"}',
        vus=10,
        duration_seconds=15,
    )
    assert "import http from 'k6/http';" in script
    assert '"vus": 10' in script
    assert '"duration": "15s"' in script
    assert "http.request(" in script
    # The URL/body/headers must appear as valid JSON string literals
    # (json.dumps output), not hand-escaped - spot check the quote survives
    # properly escaped rather than breaking out of the literal.
    assert '\\"quote\\"' in script
    assert "DROP TABLE" in script  # present, but safely inside a JSON string literal


def test_build_k6_script_null_body_for_get() -> None:
    script = performance_service.build_k6_script(
        method=HttpMethod.GET, url="https://example.com", headers={}, body=None, vus=1, duration_seconds=1
    )
    assert "http.request(\"GET\", \"https://example.com\", null, { headers: {} });" in script


def test_parse_k6_summary_extracts_expected_fields() -> None:
    # Shape verified against a real `k6 run --summary-export` output (k6
    # v0.54.0): each metric's aggregates sit directly on the metric object,
    # not nested under a "values" key - a rate metric's fraction is under
    # "value" (singular), a counter's throughput is under "rate".
    summary = {
        "metrics": {
            "http_reqs": {"count": 150, "rate": 15.0},
            "http_req_failed": {"value": 0.02, "passes": 3, "fails": 147},
            "http_req_duration": {"avg": 123.4, "p(95)": 250.6, "min": 10.1, "max": 999.9},
        }
    }
    parsed = performance_service.parse_k6_summary(summary)
    assert parsed["request_count"] == 150
    assert parsed["requests_per_second"] == 15.0
    assert parsed["error_rate"] == 0.02
    assert parsed["failed_count"] == 3  # round(150 * 0.02)
    assert parsed["avg_duration_ms"] == 123.4
    assert parsed["p95_duration_ms"] == 250.6
    assert parsed["min_duration_ms"] == 10.1
    assert parsed["max_duration_ms"] == 999.9
    assert parsed["raw_summary"] == summary


def test_parse_k6_summary_missing_metrics_is_all_none_not_a_crash() -> None:
    parsed = performance_service.parse_k6_summary({"metrics": {}})
    assert parsed["request_count"] is None
    assert parsed["error_rate"] is None
    assert parsed["failed_count"] is None
    assert parsed["avg_duration_ms"] is None


def test_parse_k6_summary_handles_garbage_input_without_raising() -> None:
    parsed = performance_service.parse_k6_summary({})
    assert parsed["request_count"] is None
    assert parsed["raw_summary"] == {}


# --- run_k6_script: not-found handling (no real k6 needed) ---------------


def test_run_k6_script_raises_clear_error_when_binary_missing(monkeypatch) -> None:
    import subprocess

    def _raise_file_not_found(*args, **kwargs):
        raise FileNotFoundError("no such file")

    monkeypatch.setattr(subprocess, "run", _raise_file_not_found)

    with pytest.raises(performance_service.K6RunError, match="k6 binary not found"):
        performance_service.run_k6_script("import http from 'k6/http';", duration_seconds=5)


# --- End-to-end run tests (own engine, real commits, monkeypatched k6) ---


async def _setup_project_with_saved_request(engine) -> dict:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        user = User(
            email=f"perf-e2e-{uuid_lib.uuid4().hex[:10]}@example.com",
            full_name="Performance E2E Test User",
            hashed_password="not-a-real-hash",
        )
        session.add(user)
        await session.flush()

        project = Project(name="Performance E2E Project")
        session.add(project)
        await session.flush()

        session.add(ProjectMember(project_id=project.id, user_id=user.id, role=ProjectRole.admin))

        collection = ApiCollection(project_id=project.id, name="Collection", created_by=user.id)
        session.add(collection)
        await session.flush()

        saved_request = SavedApiRequest(
            project_id=project.id,
            collection_id=collection.id,
            folder_id=None,
            name="Ping",
            method=HttpMethod.GET,
            url="https://example.com/ping",
            headers={},
            query_params={},
            body=None,
            environment_id=None,
            created_by=user.id,
        )
        session.add(saved_request)
        await session.flush()

        performance_test = PerformanceTest(
            project_id=project.id,
            saved_request_id=saved_request.id,
            name="E2E Load Test",
            vus=3,
            duration_seconds=5,
            created_by=user.id,
        )
        session.add(performance_test)
        await session.commit()

        return {
            "user_id": user.id,
            "project_id": project.id,
            "saved_request_id": saved_request.id,
            "performance_test_id": performance_test.id,
        }


async def _cleanup(engine, ids: dict) -> None:
    async with AsyncSession(engine, expire_on_commit=False) as cleanup:
        proj = await cleanup.get(Project, ids["project_id"])
        if proj is not None:
            await cleanup.delete(proj)
        usr = await cleanup.get(User, ids["user_id"])
        if usr is not None:
            await cleanup.delete(usr)
        await cleanup.commit()
    await engine.dispose()


async def test_trigger_run_completes_with_parsed_metrics(monkeypatch) -> None:
    database_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url, future=True)
    try:
        ids = await _setup_project_with_saved_request(engine)

        fake_metrics = {
            "request_count": 90,
            "failed_count": 0,
            "error_rate": 0.0,
            "avg_duration_ms": 42.0,
            "p95_duration_ms": 88.0,
            "min_duration_ms": 10.0,
            "max_duration_ms": 120.0,
            "requests_per_second": 18.0,
            "raw_summary": {"metrics": {"http_reqs": {"values": {"count": 90}}}},
        }

        def _fake_run_k6_script(script: str, *, duration_seconds: int) -> dict:
            assert "http.request(" in script
            return fake_metrics

        monkeypatch.setattr(performance_service, "run_k6_script", _fake_run_k6_script)

        async with AsyncSession(engine, expire_on_commit=False) as session:
            run = await performance_repository.create_run(
                session, ids["project_id"], ids["performance_test_id"], ids["user_id"]
            )

        from app.worker import run_performance_test

        # task_always_eager (set globally in conftest.py) runs this inline,
        # synchronously, before .delay() returns.
        run_performance_test.delay(str(run.id))

        async with AsyncSession(engine, expire_on_commit=False) as session:
            final = await performance_repository.get_run(
                session, ids["project_id"], ids["performance_test_id"], run.id, ids["user_id"]
            )

        assert final.status == PerformanceTestRunStatus.completed
        assert final.request_count == 90
        assert final.failed_count == 0
        assert final.error_rate == 0.0
        assert final.avg_duration_ms == 42.0
        assert final.p95_duration_ms == 88.0
        assert final.requests_per_second == 18.0
        assert final.raw_summary == fake_metrics["raw_summary"]
        assert final.started_at is not None
        assert final.completed_at is not None
        assert final.error_message is None
        # Snapshot fields reflect the test's config at trigger time.
        assert final.vus == 3
        assert final.duration_seconds == 5
    finally:
        await _cleanup(engine, ids)


async def test_trigger_run_k6_not_found_ends_failed_not_crashed(monkeypatch) -> None:
    database_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url, future=True)
    try:
        ids = await _setup_project_with_saved_request(engine)

        def _fake_run_k6_script_raises(script: str, *, duration_seconds: int) -> dict:
            raise performance_service.K6RunError(
                "k6 binary not found (looked for 'k6' on PATH). "
                "Install k6 or set K6_BINARY_PATH to point at a portable binary."
            )

        monkeypatch.setattr(performance_service, "run_k6_script", _fake_run_k6_script_raises)

        async with AsyncSession(engine, expire_on_commit=False) as session:
            run = await performance_repository.create_run(
                session, ids["project_id"], ids["performance_test_id"], ids["user_id"]
            )

        from app.worker import run_performance_test

        run_performance_test.delay(str(run.id))

        async with AsyncSession(engine, expire_on_commit=False) as session:
            final = await performance_repository.get_run(
                session, ids["project_id"], ids["performance_test_id"], run.id, ids["user_id"]
            )

        assert final.status == PerformanceTestRunStatus.failed
        assert final.error_message
        assert "k6 binary not found" in final.error_message
        assert final.completed_at is not None
        # No metrics populated on failure.
        assert final.request_count is None
        assert final.raw_summary is None
    finally:
        await _cleanup(engine, ids)


async def test_list_and_get_run_via_api(user_a: dict, client: AsyncClient, monkeypatch) -> None:
    """Covers the HTTP-reachable trigger/list/get-run endpoints, using the
    shared fixture - since this test only asserts on the immediate 201
    response shape (the `queued` row) and the list/get endpoints, it never
    needs the Celery task's separate-engine visibility that the two e2e
    tests above require, so the ordinary shared client/db_session works
    fine here. Celery's `task_always_eager` will still attempt to actually
    run the task inline; monkeypatching `run_k6_script` keeps that from
    needing a real k6 binary (its own separate-engine lookups simply won't
    find the shared-session-only rows and will no-op, which is fine - this
    test only cares about the queued run + list/get shapes)."""

    def _fake_run_k6_script(script: str, *, duration_seconds: int) -> dict:
        return {
            "request_count": 1,
            "failed_count": 0,
            "error_rate": 0.0,
            "avg_duration_ms": 1.0,
            "p95_duration_ms": 1.0,
            "min_duration_ms": 1.0,
            "max_duration_ms": 1.0,
            "requests_per_second": 1.0,
            "raw_summary": {},
        }

    monkeypatch.setattr(performance_service, "run_k6_script", _fake_run_k6_script)

    project = await _create_project(client, user_a["headers"])
    saved_request = await _create_saved_request(client, user_a["headers"], project["id"])
    created = await _create_performance_test(client, user_a["headers"], project["id"], saved_request["id"])

    resp = await client.post(f"{_base(project['id'])}/{created['id']}/runs", headers=user_a["headers"])
    assert resp.status_code == 201, resp.text
    run = resp.json()
    assert set(run.keys()) >= RUN_SUMMARY_KEYS
    assert run["performance_test_id"] == created["id"]
    assert run["vus"] == created["vus"]
    assert run["duration_seconds"] == created["duration_seconds"]

    resp = await client.get(f"{_base(project['id'])}/{created['id']}/runs", headers=user_a["headers"])
    assert resp.status_code == 200, resp.text
    runs = resp.json()
    assert len(runs) == 1
    assert set(runs[0].keys()) == RUN_SUMMARY_KEYS  # summary shape - no raw_summary

    resp = await client.get(
        f"{_base(project['id'])}/{created['id']}/runs/{run['id']}", headers=user_a["headers"]
    )
    assert resp.status_code == 200, resp.text
    full = resp.json()
    assert "raw_summary" in full  # full shape includes raw_summary


async def test_get_run_unknown_returns_404(user_a: dict, client: AsyncClient) -> None:
    project = await _create_project(client, user_a["headers"])
    saved_request = await _create_saved_request(client, user_a["headers"], project["id"])
    created = await _create_performance_test(client, user_a["headers"], project["id"], saved_request["id"])

    resp = await client.get(
        f"{_base(project['id'])}/{created['id']}/runs/{uuid_lib.uuid4()}", headers=user_a["headers"]
    )
    assert resp.status_code == 404, resp.text
