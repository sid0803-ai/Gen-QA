"""Business logic that crosses into an actual outbound HTTP call
(`httpx.AsyncClient`, async/non-blocking, run inline in the normal FastAPI
request/response cycle - NOT a Celery task, unlike the `executions` domain's
Playwright runs. This is fast and synchronous-from-the-caller's-perspective
by design; see the module docstring in `app.domains.api_performer.models`
for the full list of deliberate scope cuts (no execution history, SSRF).

Pure project-scoped persistence/authorization stays in repository.py, same
convention as every other domain's service.py.
"""
import re
import time
import uuid
from urllib.parse import urlsplit

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.api_performer.models import HttpMethod
from app.domains.environments import repository as environments_repository
from app.domains.environments.models import Environment

ALLOWED_SCHEMES = {"http", "https"}
REQUEST_TIMEOUT_SECONDS = 15.0
MAX_REDIRECTS = 5
MAX_BODY_BYTES = 1_000_000
_TRUNCATION_NOTE = "\n...[truncated - response exceeded 1MB]"

_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


class InvalidSchemeError(Exception):
    """URL scheme isn't http/https -> 400."""


def _substitute_base_url(url: str, base_url: str) -> str:
    """`{{base_url}}` is only ever substituted in the URL, per spec."""
    return url.replace("{{base_url}}", base_url)


def _substitute_variables(text: str | None, variables: dict[str, str]) -> str | None:
    """`{{KEY}}` is substituted anywhere in the URL, header values, query
    param values, or body - if `variables` has no such key, `{{KEY}}` is
    left untouched verbatim (never an error)."""
    if text is None:
        return None

    def _replace(match: re.Match) -> str:
        key = match.group(1)
        return variables.get(key, match.group(0))

    return _PLACEHOLDER_RE.sub(_replace, text)


def apply_substitution(
    *,
    url: str,
    headers: dict[str, str],
    query_params: dict[str, str],
    body: str | None,
    environment: Environment | None,
) -> tuple[str, dict[str, str], dict[str, str], str | None]:
    """Applies the variable-substitution rule for one environment (or does
    nothing if `environment` is None - any `{{...}}` placeholders are then
    sent through literally, unmodified)."""
    if environment is None:
        return url, headers, query_params, body

    substituted_url = _substitute_base_url(url, environment.base_url)
    substituted_url = _substitute_variables(substituted_url, environment.variables)
    assert substituted_url is not None  # input was non-None
    substituted_headers = {
        k: _substitute_variables(v, environment.variables) for k, v in headers.items()
    }
    substituted_query_params = {
        k: _substitute_variables(v, environment.variables) for k, v in query_params.items()
    }
    substituted_body = _substitute_variables(body, environment.variables)
    return substituted_url, substituted_headers, substituted_query_params, substituted_body


async def resolve_environment(
    db: AsyncSession, project_id: uuid.UUID, environment_id: uuid.UUID | None, user_id: uuid.UUID
) -> Environment | None:
    """None -> None (no substitution). Otherwise fetches the environment,
    scoped to this project - raises environments_repository's own
    EnvironmentNotFoundError (-> 404) if it doesn't resolve in this project."""
    if environment_id is None:
        return None
    return await environments_repository.get_environment(db, project_id, environment_id, user_id)


async def execute_http_request(
    *,
    method: HttpMethod,
    url: str,
    headers: dict[str, str],
    query_params: dict[str, str],
    body: str | None,
) -> dict:
    """Performs the actual outbound HTTP call. Never raises for a failed
    *outbound* call (timeout, connection refused, DNS failure, etc.) - those
    come back as a populated `error` in the returned dict, per the
    ExecuteResponse contract. Raises InvalidSchemeError (-> 400) for a
    non-http/https URL, since that's a caller mistake, not a network
    outcome."""
    parsed = urlsplit(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise InvalidSchemeError()

    start = time.monotonic()

    def _failure(message: str) -> dict:
        return {
            "status_code": None,
            "headers": {},
            "body": "",
            "duration_ms": 0,
            "error": message,
        }

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            max_redirects=MAX_REDIRECTS,
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as client:
            async with client.stream(
                method.value,
                url,
                headers=headers or None,
                params=query_params or None,
                content=body.encode("utf-8") if body is not None else None,
            ) as response:
                chunks: list[bytes] = []
                total = 0
                truncated = False
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > MAX_BODY_BYTES:
                        remaining = MAX_BODY_BYTES - sum(len(c) for c in chunks)
                        if remaining > 0:
                            chunks.append(chunk[:remaining])
                        truncated = True
                        break
                    chunks.append(chunk)
                raw_body = b"".join(chunks)
                response_status_code = response.status_code
                response_headers = dict(response.headers)
    except httpx.TimeoutException:
        return _failure(f"Request timed out after {REQUEST_TIMEOUT_SECONDS:.0f} seconds.")
    except httpx.RequestError as exc:
        return _failure(f"Request failed: {exc}")

    duration_ms = int((time.monotonic() - start) * 1000)
    body_text = raw_body.decode("utf-8", errors="replace")
    if truncated:
        body_text += _TRUNCATION_NOTE

    return {
        "status_code": response_status_code,
        "headers": response_headers,
        "body": body_text,
        "duration_ms": duration_ms,
        "error": None,
    }
