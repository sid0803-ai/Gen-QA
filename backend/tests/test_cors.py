"""CORS must be enabled for the frontend origin, or the browser-based app
cannot call this API at all (see backend/app/core/config.py CORS_ALLOWED_ORIGINS)."""
from httpx import AsyncClient


async def test_preflight_allows_configured_frontend_origin(client: AsyncClient) -> None:
    resp = await client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:5173"


async def test_response_includes_cors_header_for_allowed_origin(client: AsyncClient) -> None:
    resp = await client.get(
        "/health",
        headers={"Origin": "http://127.0.0.1:5173"},
    )
    assert resp.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"
