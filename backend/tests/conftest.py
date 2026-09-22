"""Shared pytest fixtures.

Uses a dedicated Postgres test database (created automatically if it doesn't
exist) with a connection-level transaction + SAVEPOINT per test, rolled back
afterwards, so tests never leak state into each other and never require
tearing down/recreating the schema between tests.
"""
import os
import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable

import asyncpg
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

# Must be set before `app.core.config.get_settings()` is first called anywhere
# (including transitively, e.g. by app.core.db at import time).
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://genqa:genqa@localhost:5432/genqa_test"
)

TEST_DATABASE_URL = os.environ["DATABASE_URL"]

from app.core.db import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402

# NOTE: we deliberately do *not* share one asyncpg engine across tests.
# create_async_engine()'s pool binds internal asyncio primitives (locks,
# futures) to whatever event loop is running when a connection is first
# checked out. pytest-asyncio gives every test function its own event loop
# by default (loop scope "function"), so an engine created in a
# session-scoped fixture and reused inside a function-scoped fixture trips
# "got Future ... attached to a different loop". Each test therefore gets
# its own short-lived engine, created and disposed within its own loop.
async def _ensure_database_exists(database_url: str) -> None:
    """Create the test database via the admin `postgres` database if missing."""
    url = make_url(database_url)
    db_name = url.database
    admin_dsn = url.set(database="postgres", drivername="postgresql").render_as_string(
        hide_password=False
    )
    conn = await asyncpg.connect(dsn=admin_dsn)
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", db_name)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        await conn.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database() -> AsyncGenerator[None, None]:
    """Create the schema once per test run, via its own short-lived engine."""
    await _ensure_database_exists(TEST_DATABASE_URL)
    engine = create_async_engine(TEST_DATABASE_URL, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    yield


@pytest_asyncio.fixture
async def db_session(setup_database: None) -> AsyncGenerator[AsyncSession, None]:
    """A fresh engine + connection-level transaction (rolled back) per test,
    all created on this test's own event loop."""
    engine = create_async_engine(TEST_DATABASE_URL, future=True)
    try:
        async with engine.connect() as connection:
            await connection.begin()
            session = AsyncSession(
                bind=connection,
                join_transaction_mode="create_savepoint",
                expire_on_commit=False,
            )
            try:
                yield session
            finally:
                await session.close()
                await connection.rollback()
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
def register_user(
    client: AsyncClient,
) -> Callable[..., Awaitable[dict]]:
    """Factory fixture: await register_user(email) -> {user, tokens, headers}."""

    async def _register(
        email: str | None = None,
        password: str = "supersecret1",
        full_name: str = "Test User",
    ) -> dict:
        email = email or f"user-{uuid.uuid4().hex[:10]}@example.com"

        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": full_name},
        )
        assert resp.status_code == 201, resp.text

        login_resp = await client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": password},
        )
        assert login_resp.status_code == 200, login_resp.text
        tokens = login_resp.json()

        return {
            "email": email,
            "password": password,
            "user": resp.json(),
            "tokens": tokens,
            "headers": {"Authorization": f"Bearer {tokens['access_token']}"},
        }

    return _register


@pytest_asyncio.fixture
async def user_a(register_user: Callable[..., Awaitable[dict]]) -> dict:
    return await register_user(email=f"user-a-{uuid.uuid4().hex[:8]}@example.com")


@pytest_asyncio.fixture
async def user_b(register_user: Callable[..., Awaitable[dict]]) -> dict:
    return await register_user(email=f"user-b-{uuid.uuid4().hex[:8]}@example.com")
