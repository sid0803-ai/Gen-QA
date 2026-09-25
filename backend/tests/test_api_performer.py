"""Tests for /api/v1/projects/{project_id}/api-requests/* (api_performer
domain): CRUD, role enforcement, project isolation, and real outbound HTTP
execution (ad-hoc + saved, with/without environment substitution, invalid
scheme rejection, unreachable-target error shape).

Uses a trivial local `http.server`-based echo server (same
"real-network-call" pattern as `tests/test_executions.py`'s
`local_http_server` fixture) that reports back exactly what it received
(method, path, query string, headers, body) as JSON, so substitution can be
asserted against what was *actually sent*, not just what the client thinks
it sent.
"""
import functools
import http.server
import json
import socket
import threading
from collections.abc import Awaitable, Callable

import pytest
from httpx import AsyncClient

READ_KEYS = {
    "id",
    "project_id",
    "collection_id",
    "folder_id",
    "name",
    "method",
    "url",
    "headers",
    "query_params",
    "body",
    "environment_id",
    "created_by",
    "created_at",
    "updated_at",
}

EXECUTE_KEYS = {"status_code", "headers", "body", "duration_ms", "error"}

COLLECTION_READ_KEYS = {"id", "project_id", "name", "created_by", "created_at", "updated_at"}
FOLDER_READ_KEYS = {"id", "collection_id", "name", "created_by", "created_at", "updated_at"}


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


async def _create_environment(
    client: AsyncClient, headers: dict, project_id: str, base_url: str, variables: dict | None = None
) -> dict:
    resp = await client.post(
        f"/api/v1/projects/{project_id}/environments",
        json={"name": "Env", "base_url": base_url, "variables": variables or {}},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _base(project_id: str) -> str:
    return f"/api/v1/projects/{project_id}/api-requests"


def _collections_base(project_id: str) -> str:
    return f"/api/v1/projects/{project_id}/api-collections"


def _folders_base(project_id: str, collection_id: str) -> str:
    return f"{_collections_base(project_id)}/{collection_id}/folders"


async def _create_collection(client: AsyncClient, auth_headers: dict, project_id: str, name: str = "Collection") -> dict:
    resp = await client.post(_collections_base(project_id), json={"name": name}, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_folder(
    client: AsyncClient, auth_headers: dict, project_id: str, collection_id: str, name: str = "Folder"
) -> dict:
    resp = await client.post(_folders_base(project_id, collection_id), json={"name": name}, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_saved_request(client: AsyncClient, auth_headers: dict, project_id: str, **overrides) -> dict:
    if "collection_id" not in overrides:
        collection = await _create_collection(client, auth_headers, project_id)
        overrides = {**overrides, "collection_id": collection["id"]}
    body = {"name": "Ping", "method": "GET", "url": "https://example.com/ping"}
    body.update(overrides)
    resp = await client.post(_base(project_id), json=body, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- Echo server -------------------------------------------------------


class _EchoHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A002
        pass

    def _handle(self) -> None:
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw_body = self.rfile.read(length) if length else b""
        payload = {
            "method": self.command,
            "path": self.path,
            "headers": {k: v for k, v in self.headers.items()},
            "body": raw_body.decode("utf-8", errors="replace"),
        }
        response_bytes = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response_bytes)))
        self.end_headers()
        self.wfile.write(response_bytes)

    def do_GET(self) -> None:
        self._handle()

    def do_POST(self) -> None:
        self._handle()

    def do_PUT(self) -> None:
        self._handle()

    def do_PATCH(self) -> None:
        self._handle()

    def do_DELETE(self) -> None:
        self._handle()


@pytest.fixture
def echo_server():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _EchoHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture
def unreachable_url() -> str:
    """A local port nothing is listening on -> ECONNREFUSED fast (no need to
    wait out the real 15s timeout to prove the error path)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return f"http://127.0.0.1:{port}/nope"


# --- CRUD ----------------------------------------------------------------


async def test_create_full_shape(register_user: Callable[..., Awaitable[dict]], client: AsyncClient) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])

    saved = await _create_saved_request(
        client,
        owner["headers"],
        project["id"],
        headers={"X-Test": "1"},
        query_params={"q": "1"},
        body="hello",
    )
    assert set(saved.keys()) == READ_KEYS
    assert saved["name"] == "Ping"
    assert saved["method"] == "GET"
    assert saved["url"] == "https://example.com/ping"
    assert saved["headers"] == {"X-Test": "1"}
    assert saved["query_params"] == {"q": "1"}
    assert saved["body"] == "hello"
    assert saved["environment_id"] is None
    assert saved["created_by"] == owner["user"]["id"]


async def test_defaults(register_user: Callable[..., Awaitable[dict]], client: AsyncClient) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    collection = await _create_collection(client, owner["headers"], project["id"])
    resp = await client.post(
        _base(project["id"]),
        json={
            "name": "Bare",
            "method": "GET",
            "url": "https://example.com",
            "collection_id": collection["id"],
        },
        headers=owner["headers"],
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["headers"] == {}
    assert body["query_params"] == {}
    assert body["body"] is None


async def test_list_newest_first_and_get(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    r1 = await _create_saved_request(client, owner["headers"], project["id"], name="First")
    r2 = await _create_saved_request(client, owner["headers"], project["id"], name="Second")

    list_resp = await client.get(_base(project["id"]), headers=owner["headers"])
    assert list_resp.status_code == 200
    assert [r["id"] for r in list_resp.json()] == [r2["id"], r1["id"]]

    get_resp = await client.get(f"{_base(project['id'])}/{r1['id']}", headers=owner["headers"])
    assert get_resp.status_code == 200
    assert get_resp.json() == r1

    missing = await client.get(f"{_base(project['id'])}/00000000-0000-0000-0000-000000000000", headers=owner["headers"])
    assert missing.status_code == 404


async def test_patch_updates_subset(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    saved = await _create_saved_request(client, owner["headers"], project["id"])

    patch_resp = await client.patch(
        f"{_base(project['id'])}/{saved['id']}",
        json={"method": "POST", "headers": {"A": "B"}},
        headers=owner["headers"],
    )
    assert patch_resp.status_code == 200
    updated = patch_resp.json()
    assert updated["method"] == "POST"
    assert updated["headers"] == {"A": "B"}
    assert updated["url"] == saved["url"]  # untouched
    assert updated["name"] == saved["name"]  # untouched


async def test_delete(register_user: Callable[..., Awaitable[dict]], client: AsyncClient) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    saved = await _create_saved_request(client, owner["headers"], project["id"])

    delete_resp = await client.delete(f"{_base(project['id'])}/{saved['id']}", headers=owner["headers"])
    assert delete_resp.status_code == 204

    get_resp = await client.get(f"{_base(project['id'])}/{saved['id']}", headers=owner["headers"])
    assert get_resp.status_code == 404


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
    collection = await _create_collection(client, owner["headers"], project["id"])

    create_viewer = await client.post(
        _base(project["id"]),
        json={
            "name": "X",
            "method": "GET",
            "url": "https://example.com",
            "collection_id": collection["id"],
        },
        headers=viewer["headers"],
    )
    assert create_viewer.status_code == 403

    list_stranger = await client.get(_base(project["id"]), headers=stranger["headers"])
    assert list_stranger.status_code == 404

    saved = await _create_saved_request(client, owner["headers"], project["id"])

    patch_viewer = await client.patch(
        f"{_base(project['id'])}/{saved['id']}", json={"name": "x"}, headers=viewer["headers"]
    )
    assert patch_viewer.status_code == 403

    delete_member = await client.delete(f"{_base(project['id'])}/{saved['id']}", headers=member["headers"])
    assert delete_member.status_code == 403

    delete_admin = await client.delete(f"{_base(project['id'])}/{saved['id']}", headers=owner["headers"])
    assert delete_admin.status_code == 204


async def test_project_isolation(user_a: dict, user_b: dict, client: AsyncClient) -> None:
    project_b = await _create_project(client, user_b["headers"], "B's project")
    saved = await _create_saved_request(client, user_b["headers"], project_b["id"])
    base_b = _base(project_b["id"])

    assert (await client.get(base_b, headers=user_a["headers"])).status_code == 404
    assert (await client.get(f"{base_b}/{saved['id']}", headers=user_a["headers"])).status_code == 404
    assert (
        await client.post(
            base_b,
            json={
                "name": "x",
                "method": "GET",
                "url": "https://x.example.com",
                "collection_id": saved["collection_id"],
            },
            headers=user_a["headers"],
        )
    ).status_code == 404
    assert (
        await client.patch(f"{base_b}/{saved['id']}", json={"name": "hijacked"}, headers=user_a["headers"])
    ).status_code == 404
    assert (await client.delete(f"{base_b}/{saved['id']}", headers=user_a["headers"])).status_code == 404


# --- Collections/Folders (Sprint 9) ---------------------------------------


async def test_collection_crud_and_role_enforcement(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    viewer = await register_user()
    await _add_member(client, owner["headers"], project["id"], viewer["email"], "viewer")
    member = await register_user()
    await _add_member(client, owner["headers"], project["id"], member["email"], "member")

    create_viewer = await client.post(
        _collections_base(project["id"]), json={"name": "X"}, headers=viewer["headers"]
    )
    assert create_viewer.status_code == 403

    collection = await _create_collection(client, owner["headers"], project["id"], name="Suite A")
    assert set(collection.keys()) == COLLECTION_READ_KEYS
    assert collection["name"] == "Suite A"
    assert collection["project_id"] == project["id"]
    assert collection["created_by"] == owner["user"]["id"]

    second = await _create_collection(client, owner["headers"], project["id"], name="Suite B")
    list_resp = await client.get(_collections_base(project["id"]), headers=owner["headers"])
    assert list_resp.status_code == 200
    assert [c["id"] for c in list_resp.json()] == [second["id"], collection["id"]]

    patch_viewer = await client.patch(
        f"{_collections_base(project['id'])}/{collection['id']}",
        json={"name": "nope"},
        headers=viewer["headers"],
    )
    assert patch_viewer.status_code == 403

    patch_resp = await client.patch(
        f"{_collections_base(project['id'])}/{collection['id']}",
        json={"name": "Renamed"},
        headers=member["headers"],
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "Renamed"

    delete_member = await client.delete(
        f"{_collections_base(project['id'])}/{collection['id']}", headers=member["headers"]
    )
    assert delete_member.status_code == 403

    delete_admin = await client.delete(
        f"{_collections_base(project['id'])}/{collection['id']}", headers=owner["headers"]
    )
    assert delete_admin.status_code == 204

    missing_patch = await client.patch(
        f"{_collections_base(project['id'])}/{collection['id']}",
        json={"name": "x"},
        headers=owner["headers"],
    )
    assert missing_patch.status_code == 404


async def test_collection_project_isolation(user_a: dict, user_b: dict, client: AsyncClient) -> None:
    project_b = await _create_project(client, user_b["headers"], "B's project")
    collection = await _create_collection(client, user_b["headers"], project_b["id"])
    base_b = _collections_base(project_b["id"])

    assert (await client.get(base_b, headers=user_a["headers"])).status_code == 404
    assert (
        await client.post(base_b, json={"name": "x"}, headers=user_a["headers"])
    ).status_code == 404
    assert (
        await client.patch(f"{base_b}/{collection['id']}", json={"name": "hijack"}, headers=user_a["headers"])
    ).status_code == 404
    assert (await client.delete(f"{base_b}/{collection['id']}", headers=user_a["headers"])).status_code == 404


async def test_delete_collection_cascades_to_folders_and_requests(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    collection = await _create_collection(client, owner["headers"], project["id"])
    folder = await _create_folder(client, owner["headers"], project["id"], collection["id"])
    saved = await _create_saved_request(
        client, owner["headers"], project["id"], collection_id=collection["id"], folder_id=folder["id"]
    )

    delete_resp = await client.delete(
        f"{_collections_base(project['id'])}/{collection['id']}", headers=owner["headers"]
    )
    assert delete_resp.status_code == 204

    assert (
        await client.get(f"{_base(project['id'])}/{saved['id']}", headers=owner["headers"])
    ).status_code == 404
    assert (
        await client.get(_folders_base(project["id"], collection["id"]), headers=owner["headers"])
    ).status_code == 404


async def test_folder_crud_role_enforcement_and_404s(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    viewer = await register_user()
    await _add_member(client, owner["headers"], project["id"], viewer["email"], "viewer")
    member = await register_user()
    await _add_member(client, owner["headers"], project["id"], member["email"], "member")
    collection = await _create_collection(client, owner["headers"], project["id"])

    missing_collection = await client.post(
        f"{_collections_base(project['id'])}/00000000-0000-0000-0000-000000000000/folders",
        json={"name": "X"},
        headers=owner["headers"],
    )
    assert missing_collection.status_code == 404

    create_viewer = await client.post(
        _folders_base(project["id"], collection["id"]), json={"name": "X"}, headers=viewer["headers"]
    )
    assert create_viewer.status_code == 403

    folder = await _create_folder(client, owner["headers"], project["id"], collection["id"], name="Auth")
    assert set(folder.keys()) == FOLDER_READ_KEYS
    assert folder["collection_id"] == collection["id"]

    second_folder = await _create_folder(client, owner["headers"], project["id"], collection["id"], name="Users")
    list_resp = await client.get(_folders_base(project["id"], collection["id"]), headers=owner["headers"])
    assert list_resp.status_code == 200
    assert [f["id"] for f in list_resp.json()] == [second_folder["id"], folder["id"]]

    patch_resp = await client.patch(
        f"{_folders_base(project['id'], collection['id'])}/{folder['id']}",
        json={"name": "Renamed"},
        headers=member["headers"],
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "Renamed"

    delete_viewer = await client.delete(
        f"{_folders_base(project['id'], collection['id'])}/{folder['id']}", headers=viewer["headers"]
    )
    assert delete_viewer.status_code == 403

    delete_admin = await client.delete(
        f"{_folders_base(project['id'], collection['id'])}/{folder['id']}", headers=owner["headers"]
    )
    assert delete_admin.status_code == 204

    missing_folder = await client.get(
        f"{_folders_base(project['id'], collection['id'])}",
        headers=owner["headers"],
    )
    assert missing_folder.status_code == 200
    assert missing_folder.json() == [second_folder]


async def test_delete_folder_unfiles_requests_instead_of_deleting_them(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    collection = await _create_collection(client, owner["headers"], project["id"])
    folder = await _create_folder(client, owner["headers"], project["id"], collection["id"])
    saved = await _create_saved_request(
        client, owner["headers"], project["id"], collection_id=collection["id"], folder_id=folder["id"]
    )
    assert saved["folder_id"] == folder["id"]

    delete_resp = await client.delete(
        f"{_folders_base(project['id'], collection['id'])}/{folder['id']}", headers=owner["headers"]
    )
    assert delete_resp.status_code == 204

    get_resp = await client.get(f"{_base(project['id'])}/{saved['id']}", headers=owner["headers"])
    assert get_resp.status_code == 200
    assert get_resp.json()["folder_id"] is None
    assert get_resp.json()["collection_id"] == collection["id"]


async def test_create_request_requires_valid_collection_and_folder(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    collection = await _create_collection(client, owner["headers"], project["id"])
    other_collection = await _create_collection(client, owner["headers"], project["id"], name="Other")
    folder_in_other = await _create_folder(client, owner["headers"], project["id"], other_collection["id"])

    missing_collection = await client.post(
        _base(project["id"]),
        json={
            "name": "X",
            "method": "GET",
            "url": "https://example.com",
            "collection_id": "00000000-0000-0000-0000-000000000000",
        },
        headers=owner["headers"],
    )
    assert missing_collection.status_code == 404

    missing_folder = await client.post(
        _base(project["id"]),
        json={
            "name": "X",
            "method": "GET",
            "url": "https://example.com",
            "collection_id": collection["id"],
            "folder_id": "00000000-0000-0000-0000-000000000000",
        },
        headers=owner["headers"],
    )
    assert missing_folder.status_code == 404

    mismatched_folder = await client.post(
        _base(project["id"]),
        json={
            "name": "X",
            "method": "GET",
            "url": "https://example.com",
            "collection_id": collection["id"],
            "folder_id": folder_in_other["id"],
        },
        headers=owner["headers"],
    )
    assert mismatched_folder.status_code == 400
    assert "Folder does not belong" in mismatched_folder.json()["detail"]

    ok = await client.post(
        _base(project["id"]),
        json={
            "name": "X",
            "method": "GET",
            "url": "https://example.com",
            "collection_id": collection["id"],
        },
        headers=owner["headers"],
    )
    # Sanity: a valid collection_id with no folder_id succeeds.
    assert ok.status_code == 201, ok.text


async def test_patch_folder_id_omitted_vs_explicit_null(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    """The one deliberate exception to the blanket PATCH convention: omitting
    `folder_id` leaves it unchanged, but sending it explicitly as `null`
    clears it back to the collection's top level."""
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    collection = await _create_collection(client, owner["headers"], project["id"])
    folder = await _create_folder(client, owner["headers"], project["id"], collection["id"])
    saved = await _create_saved_request(
        client, owner["headers"], project["id"], collection_id=collection["id"], folder_id=folder["id"]
    )
    assert saved["folder_id"] == folder["id"]

    # Omitted entirely - folder_id stays the same.
    patch_omitted = await client.patch(
        f"{_base(project['id'])}/{saved['id']}", json={"name": "renamed"}, headers=owner["headers"]
    )
    assert patch_omitted.status_code == 200
    assert patch_omitted.json()["folder_id"] == folder["id"]
    assert patch_omitted.json()["name"] == "renamed"

    # Explicit null - folder_id cleared to top level.
    patch_null = await client.patch(
        f"{_base(project['id'])}/{saved['id']}", json={"folder_id": None}, headers=owner["headers"]
    )
    assert patch_null.status_code == 200
    assert patch_null.json()["folder_id"] is None
    assert patch_null.json()["collection_id"] == collection["id"]

    # Set to a new folder within the same collection.
    other_folder = await _create_folder(client, owner["headers"], project["id"], collection["id"], name="Other")
    patch_set = await client.patch(
        f"{_base(project['id'])}/{saved['id']}",
        json={"folder_id": other_folder["id"]},
        headers=owner["headers"],
    )
    assert patch_set.status_code == 200
    assert patch_set.json()["folder_id"] == other_folder["id"]

    # Set to a folder that belongs to a different collection -> 400.
    other_collection = await _create_collection(client, owner["headers"], project["id"], name="Other Coll")
    folder_elsewhere = await _create_folder(client, owner["headers"], project["id"], other_collection["id"])
    patch_mismatch = await client.patch(
        f"{_base(project['id'])}/{saved['id']}",
        json={"folder_id": folder_elsewhere["id"]},
        headers=owner["headers"],
    )
    assert patch_mismatch.status_code == 400

    # Set to a nonexistent folder -> 404.
    patch_missing = await client.patch(
        f"{_base(project['id'])}/{saved['id']}",
        json={"folder_id": "00000000-0000-0000-0000-000000000000"},
        headers=owner["headers"],
    )
    assert patch_missing.status_code == 404


async def test_tree_endpoint_shape_and_request_appears_exactly_once(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    stranger = await register_user()

    collection = await _create_collection(client, owner["headers"], project["id"], name="Suite")
    folder = await _create_folder(client, owner["headers"], project["id"], collection["id"], name="Auth")
    top_level = await _create_saved_request(
        client, owner["headers"], project["id"], collection_id=collection["id"], name="Top", method="GET"
    )
    filed = await _create_saved_request(
        client,
        owner["headers"],
        project["id"],
        collection_id=collection["id"],
        folder_id=folder["id"],
        name="Filed",
        method="POST",
    )
    empty_collection = await _create_collection(client, owner["headers"], project["id"], name="Empty")

    tree_resp = await client.get(f"{_collections_base(project['id'])}/tree", headers=owner["headers"])
    assert tree_resp.status_code == 200
    tree = tree_resp.json()
    assert [c["id"] for c in tree] == [empty_collection["id"], collection["id"]]

    suite_node = next(c for c in tree if c["id"] == collection["id"])
    assert set(suite_node.keys()) == {"id", "name", "requests", "folders"}
    assert [r["id"] for r in suite_node["requests"]] == [top_level["id"]]
    assert suite_node["requests"][0] == {"id": top_level["id"], "name": "Top", "method": "GET"}

    assert len(suite_node["folders"]) == 1
    folder_node = suite_node["folders"][0]
    assert set(folder_node.keys()) == {"id", "name", "requests"}
    assert folder_node["id"] == folder["id"]
    assert [r["id"] for r in folder_node["requests"]] == [filed["id"]]
    assert folder_node["requests"][0] == {"id": filed["id"], "name": "Filed", "method": "POST"}

    empty_node = next(c for c in tree if c["id"] == empty_collection["id"])
    assert empty_node["requests"] == []
    assert empty_node["folders"] == []

    # A stranger to the project can't see the tree at all.
    stranger_resp = await client.get(f"{_collections_base(project['id'])}/tree", headers=stranger["headers"])
    assert stranger_resp.status_code == 404


# --- Execution -------------------------------------------------------------


async def test_ad_hoc_execute_against_real_server(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient, echo_server: str
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])

    resp = await client.post(
        f"{_base(project['id'])}/execute",
        json={
            "method": "POST",
            "url": f"{echo_server}/hello?a=1",
            "headers": {"X-Custom": "yes"},
            "body": "raw-body-text",
        },
        headers=owner["headers"],
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == EXECUTE_KEYS
    assert body["status_code"] == 200
    assert body["error"] is None
    assert body["duration_ms"] >= 0
    echoed = json.loads(body["body"])
    assert echoed["method"] == "POST"
    assert echoed["path"] == "/hello?a=1"
    assert echoed["headers"]["X-Custom"] == "yes"
    assert echoed["body"] == "raw-body-text"


async def test_execute_substitutes_base_url_and_variables(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient, echo_server: str
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    environment = await _create_environment(
        client, owner["headers"], project["id"], echo_server, variables={"TOKEN": "secret-123", "PATH_PART": "widgets"}
    )

    resp = await client.post(
        f"{_base(project['id'])}/execute",
        json={
            "method": "GET",
            "url": "{{base_url}}/{{PATH_PART}}?token={{TOKEN}}",
            "headers": {"Authorization": "Bearer {{TOKEN}}"},
            "query_params": {"extra": "{{TOKEN}}"},
            "body": "payload with {{TOKEN}} inside",
            "environment_id": environment["id"],
        },
        headers=owner["headers"],
    )
    assert resp.status_code == 200, resp.text
    echoed = json.loads(resp.json()["body"])
    assert echoed["path"].startswith("/widgets?")
    assert "token=secret-123" in echoed["path"]
    assert "extra=secret-123" in echoed["path"]
    assert echoed["headers"]["Authorization"] == "Bearer secret-123"
    assert echoed["body"] == "payload with secret-123 inside"


async def test_execute_unknown_variable_left_untouched(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient, echo_server: str
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    environment = await _create_environment(client, owner["headers"], project["id"], echo_server, variables={})

    resp = await client.post(
        f"{_base(project['id'])}/execute",
        json={
            "method": "GET",
            "url": "{{base_url}}/path?missing={{NOT_SET}}",
            "environment_id": environment["id"],
        },
        headers=owner["headers"],
    )
    assert resp.status_code == 200, resp.text
    echoed = json.loads(resp.json()["body"])
    assert echoed["path"] == "/path?missing=%7B%7BNOT_SET%7D%7D" or "{{NOT_SET}}" in echoed["path"]


async def test_execute_saved_request_uses_own_environment_by_default(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient, echo_server: str
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    environment = await _create_environment(client, owner["headers"], project["id"], echo_server, variables={"K": "v1"})
    saved = await _create_saved_request(
        client,
        owner["headers"],
        project["id"],
        url="{{base_url}}/from-saved",
        headers={"H": "{{K}}"},
        environment_id=environment["id"],
    )

    resp = await client.post(f"{_base(project['id'])}/{saved['id']}/execute", headers=owner["headers"])
    assert resp.status_code == 200, resp.text
    echoed = json.loads(resp.json()["body"])
    assert echoed["path"] == "/from-saved"
    assert echoed["headers"]["H"] == "v1"


async def test_execute_saved_request_environment_override(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient, echo_server: str
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    env_a = await _create_environment(client, owner["headers"], project["id"], "https://unused.example.com", variables={"K": "from-a"})
    env_b = await _create_environment(client, owner["headers"], project["id"], echo_server, variables={"K": "from-b"})
    saved = await _create_saved_request(
        client,
        owner["headers"],
        project["id"],
        url="{{base_url}}/override",
        headers={"H": "{{K}}"},
        environment_id=env_a["id"],
    )

    resp = await client.post(
        f"{_base(project['id'])}/{saved['id']}/execute",
        json={"environment_id": env_b["id"]},
        headers=owner["headers"],
    )
    assert resp.status_code == 200, resp.text
    echoed = json.loads(resp.json()["body"])
    assert echoed["path"] == "/override"
    assert echoed["headers"]["H"] == "from-b"


async def test_execute_does_not_persist_anything(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient, echo_server: str
) -> None:
    """Explicit scope-cut proof: no execution-history record shows up
    anywhere after an execute call - there is no such endpoint/table to
    even check, by design (see module docstring)."""
    owner = await register_user()
    project = await _create_project(client, owner["headers"])

    before = await client.get(_base(project["id"]), headers=owner["headers"])
    resp = await client.post(
        f"{_base(project['id'])}/execute",
        json={"method": "GET", "url": echo_server},
        headers=owner["headers"],
    )
    assert resp.status_code == 200
    after = await client.get(_base(project["id"]), headers=owner["headers"])
    assert before.json() == after.json() == []


async def test_execute_rejects_invalid_scheme(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])

    resp = await client.post(
        f"{_base(project['id'])}/execute",
        json={"method": "GET", "url": "ftp://example.com/file"},
        headers=owner["headers"],
    )
    assert resp.status_code == 400, resp.text
    assert "http/https" in resp.json()["detail"]


async def test_execute_unreachable_target_returns_populated_error_not_500(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient, unreachable_url: str
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])

    resp = await client.post(
        f"{_base(project['id'])}/execute",
        json={"method": "GET", "url": unreachable_url},
        headers=owner["headers"],
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == EXECUTE_KEYS
    assert body["status_code"] is None
    assert body["headers"] == {}
    assert body["body"] == ""
    assert body["duration_ms"] == 0
    assert body["error"]


async def test_execute_unknown_environment_returns_404(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])

    resp = await client.post(
        f"{_base(project['id'])}/execute",
        json={
            "method": "GET",
            "url": "https://example.com",
            "environment_id": "00000000-0000-0000-0000-000000000000",
        },
        headers=owner["headers"],
    )
    assert resp.status_code == 404


async def test_execute_requires_member_role(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient, echo_server: str
) -> None:
    owner = await register_user()
    project = await _create_project(client, owner["headers"])
    viewer = await register_user()
    await _add_member(client, owner["headers"], project["id"], viewer["email"], "viewer")

    resp = await client.post(
        f"{_base(project['id'])}/execute",
        json={"method": "GET", "url": echo_server},
        headers=viewer["headers"],
    )
    assert resp.status_code == 403


async def test_response_body_truncated_when_oversized(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    """A pathologically large response is capped, not fully buffered."""
    big_payload = "x" * (1_500_000)

    class _BigHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:  # noqa: A002
            pass

        def do_GET(self) -> None:
            data = big_payload.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _BigHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        owner = await register_user()
        project = await _create_project(client, owner["headers"])
        resp = await client.post(
            f"{_base(project['id'])}/execute",
            json={"method": "GET", "url": f"http://127.0.0.1:{server.server_port}/big"},
            headers=owner["headers"],
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status_code"] == 200
        assert len(body["body"]) < len(big_payload)
        assert "truncated" in body["body"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
