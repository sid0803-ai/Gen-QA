"""Tests for /api/v1/auth/* (registration, login, refresh, me)."""
from collections.abc import Awaitable, Callable

from httpx import AsyncClient


async def test_register_returns_user_without_password(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "alice@example.com", "password": "supersecret1", "full_name": "Alice"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "alice@example.com"
    assert body["full_name"] == "Alice"
    assert "id" in body
    assert "password" not in body
    assert "hashed_password" not in body


async def test_register_duplicate_email_returns_409(client: AsyncClient) -> None:
    payload = {"email": "bob@example.com", "password": "supersecret1", "full_name": "Bob"}
    first = await client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201

    second = await client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409


async def test_login_success_returns_token_pair(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    account = await register_user(email="carol@example.com", password="supersecret1")

    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": account["email"], "password": "supersecret1"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]


async def test_login_bad_password_returns_401(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    account = await register_user(email="dave@example.com", password="supersecret1")

    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": account["email"], "password": "wrong-password"},
    )
    assert resp.status_code == 401


async def test_login_unknown_email_returns_401(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "nobody@example.com", "password": "whatever1"},
    )
    assert resp.status_code == 401


async def test_refresh_returns_new_token_pair(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    account = await register_user()

    resp = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": account["tokens"]["refresh_token"]}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"


async def test_refresh_rejects_access_token(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    account = await register_user()

    resp = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": account["tokens"]["access_token"]}
    )
    assert resp.status_code == 401


async def test_refresh_rejects_garbage_token(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-real-token"})
    assert resp.status_code == 401


async def test_me_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_me_returns_current_user(
    register_user: Callable[..., Awaitable[dict]], client: AsyncClient
) -> None:
    account = await register_user(email="erin@example.com", full_name="Erin")

    resp = await client.get("/api/v1/auth/me", headers=account["headers"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "erin@example.com"
    assert body["full_name"] == "Erin"
