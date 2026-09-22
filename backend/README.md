# Gen-QA Backend — Sprint 1 (Foundation)

FastAPI modular-monolith backend. Sprint 1 implements two domains:

- **identity** — user registration, login (OAuth2 password flow), JWT access/refresh
  tokens, `GET /auth/me`.
- **projects** — projects and project membership (roles: `admin` > `member` > `viewer`),
  with project membership as the sole data-isolation boundary for now.

Every future domain (requirements, test cases, executions, ...) will be added the
same way: `app/domains/<name>/{models,schemas,service,router}.py`, mounted under
`/api/v1` in `app/main.py`, and — if it stores project-scoped data — reading/writing
through a `repository.py` that always takes `project_id` + the requesting user's id
and enforces membership via `app.domains.projects.repository.require_membership`
(or the `require_project_role` dependency in `app/core/deps.py`).

## Stack

Python 3.12, FastAPI, SQLAlchemy 2.0 (async, `asyncpg` driver), Alembic, Pydantic v2,
PyJWT + passlib[bcrypt], pytest + httpx + pytest-asyncio.

## Project layout

```
backend/
  app/
    main.py                      FastAPI app, routers mounted under /api/v1
    core/
      config.py                  Settings (env vars / .env)
      security.py                Password hashing, JWT encode/decode
      db.py                      Async engine/session, get_db dependency
      deps.py                    get_current_user, require_project_role(min_role)
    domains/
      identity/                  User model, auth endpoints
      projects/                  Project, ProjectMember, membership-enforced repository
  alembic/                       Migrations
  tests/                         pytest suite (incl. test_project_isolation.py)
  Dockerfile
  requirements.txt / requirements-dev.txt
  .env.example
```

## 1. Configure environment

Copy the example env file and fill in real values (at minimum, change
`JWT_SECRET_KEY`):

```bash
cp backend/.env.example backend/.env
```

`backend/.env` is git-ignored. When you run the whole stack via the root
`docker-compose.yml`, `DATABASE_URL` and `REDIS_URL` are overridden automatically
to point at the `postgres`/`redis` containers — the values in `.env` for those two
only matter when running the backend directly on your host.

## 2. Run Postgres (and Redis, wired for future sprints)

From the repo root:

```bash
docker compose up -d postgres redis
```

## 3. Install dependencies (local/host dev)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

## 4. Run database migrations

Migrations read `DATABASE_URL` from `backend/.env` (or the environment) via
`app.core.config.Settings`, so run this with `backend/.env` pointing at a
reachable Postgres (e.g. `postgresql+asyncpg://genqa:genqa@localhost:5432/genqa`
if you exposed the `postgres` service on localhost, which the root
docker-compose.yml does on port 5432):

```bash
cd backend
alembic upgrade head
```

To generate a new migration after changing models:

```bash
alembic revision --autogenerate -m "add something"
alembic upgrade head
```

## 5. Run the dev server

Either directly:

```bash
cd backend
uvicorn app.main:app --reload
```

or via the full stack (build + run backend against the compose network,
matching the `DATABASE_URL`/`REDIS_URL` the container will actually use):

```bash
docker compose up --build backend
```

The API is served at `http://localhost:8000`, under `/api/v1`. Interactive docs at
`http://localhost:8000/docs`. Health check at `GET /health`.

## 6. Run tests

Tests use a **separate** Postgres database (`genqa_test` by default) and wrap each
test in a rolled-back transaction (SAVEPOINT), so the schema is created once per
test run and no test leaks data into another. The test database is created
automatically if it doesn't exist yet (connecting to the same Postgres server as
`DATABASE_URL`, via the `postgres` admin database).

```bash
cd backend
docker compose up -d postgres   # from repo root, if not already running
pip install -r requirements-dev.txt
pytest
```

To point tests at a different database, set `DATABASE_URL` before running pytest
(it takes precedence over the default `genqa_test` URL baked into `tests/conftest.py`):

```bash
DATABASE_URL=postgresql+asyncpg://genqa:genqa@localhost:5432/genqa_test pytest
```

`tests/test_project_isolation.py` is the critical suite: it proves user A gets a
plain 404 (never 403, never data) on every read/write path into user B's project,
and that `GET /projects` for user A never includes user B's projects.

## API contract summary

Base path: `/api/v1`

**Auth**
- `POST /auth/register` — `{email, password, full_name}` → 201 `{id, email, full_name}`; 409 on duplicate email.
- `POST /auth/login` — form-encoded `username`/`password` (OAuth2) → 200 `{access_token, refresh_token, token_type}`; 401 on bad credentials.
- `POST /auth/refresh` — `{refresh_token}` → 200 new token pair; 401 if invalid/expired.
- `GET /auth/me` — Bearer auth → 200 `{id, email, full_name}`.

**Projects** (roles: `admin` > `member` > `viewer`)
- `POST /projects` — `{name, description?}` → 201; creator becomes `admin`.
- `GET /projects` — 200 list of the caller's projects, each with their `role`.
- `GET /projects/{id}` — 200 if a member, else 404 (never 403 — no existence leak).
- `PATCH /projects/{id}` — admin only → 200; 403 if member/viewer, 404 if not a member.
- `DELETE /projects/{id}` — admin only → 204.
- `GET /projects/{id}/members` — any member → 200 list.
- `POST /projects/{id}/members` — admin only, `{email, role}`; 404 if no such registered user, 409 if already a member.
- `PATCH /projects/{id}/members/{user_id}` — admin only, `{role}`; 409 if it would leave the project with zero admins.
- `DELETE /projects/{id}/members/{user_id}` — admin only; same last-admin protection, 409.

## Deviations from the original spec

- **Last-admin protection is general, not just self-demotion.** The spec's example
  was "prevent a project's last remaining admin from demoting themselves." The
  implementation blocks removing the *last* admin's admin status (via role change
  or removal) regardless of whether they're acting on themselves or another admin
  demotes/removes them — otherwise a two-admin project could still be dropped to
  zero admins by one admin demoting/removing the other. This is a strict superset
  of the required behavior.
- Everything else follows the spec's API contract and architecture as written.
