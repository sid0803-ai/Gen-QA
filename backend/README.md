# Gen-QA Backend — Sprint 1 + Sprint 2 + Sprint 3

FastAPI modular-monolith backend. Sprint 1 implemented two domains, Sprint 2 added two
more, and Sprint 3 extends the `requirements`/`ai` domains with the next two steps in
the pipeline (Feasibility Study, Test Strategy):

- **identity** (Sprint 1) — user registration, login (OAuth2 password flow), JWT
  access/refresh tokens, `GET /auth/me`.
- **projects** (Sprint 1) — projects and project membership (roles: `admin` >
  `member` > `viewer`), with project membership as the sole data-isolation boundary.
- **requirements** (Sprint 2, extended Sprint 3) — project-scoped requirements
  (title, description, business objective, acceptance criteria, priority) and three
  parallel AI-assisted review lifecycles hanging off each requirement, all sharing the
  same draft → approved/rejected shape (editable while draft): `ai_analyses`
  (Sprint 2), `feasibility_studies` and `test_strategies` (Sprint 3).
- **ai** (Sprint 2, extended Sprint 3) — the `AIProvider` abstraction + `AIService`
  that generates a structured payload for a requirement: `RequirementAnalysisPayload`
  (Sprint 2), and `FeasibilityStudyPayload` / `TestStrategyPayload` (Sprint 3). Only a
  `MockAIProvider` (keyword-heuristic, no real LLM call) exists so far; a real
  provider can be added later without changing any caller. This domain has no
  database model of its own — `AIAnalysis`/`FeasibilityStudy`/`TestStrategy` (the
  persisted results) all live in the `requirements` domain, since their lifecycle
  (draft/approve/reject, edit-while-draft, multi-record history) is a
  requirements-domain concern, not an ai-domain one.

Every future domain (test design, executions, ...) will be added the same way:
`app/domains/<name>/{models,schemas,service,router}.py`, mounted under `/api/v1` in
`app/main.py`, and — if it stores project-scoped data — reading/writing through a
`repository.py` that always takes `project_id` + the requesting user's id and
enforces membership via `app.domains.projects.repository.require_membership` (or the
`require_project_role` dependency in `app/core/deps.py`).

**Sprint 3 domain-placement decision**: `FeasibilityStudy` and `TestStrategy` were
added as two more tables/model classes inside `app/domains/requirements/` (models,
repository, schemas, service, router), exactly alongside `AIAnalysis` rather than in
a new `app/domains/feasibility/` or `app/domains/strategy/`. This directly follows
Sprint 2's own precedent and stated rationale (see above): the interesting complexity
of these records is the human-review lifecycle tied 1:1 to a requirement's own
access control, not the AI generation step itself (which stays entirely inside
`app.domains.ai`). Splitting them into their own domains would have meant either
duplicating the requirement-membership-check plumbing three times or introducing
cross-domain repository calls for no real isolation benefit, since a
`FeasibilityStudy`/`TestStrategy` can never be read/written independently of "the
Requirement it belongs to, inside a Project the caller is a member of."

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
      requirements/               Requirement + AIAnalysis + FeasibilityStudy + TestStrategy
                                    models, CRUD + all three review lifecycles
      ai/                          AIProvider ABC, MockAIProvider, AIService
  alembic/                       Migrations
  tests/                         pytest suite (incl. test_project_isolation.py,
                                   test_feasibility.py, test_strategy.py)
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

**Requirements** (nested under a project; roles as above — `viewer` reads, `member`
create/update, `admin` delete)
- `POST /projects/{id}/requirements` — `{title, description, business_objective?, acceptance_criteria?, priority?}` (`priority` defaults `medium`) → 201 full requirement.
- `GET /projects/{id}/requirements` → 200 list `[{id, title, priority, latest_analysis_status, latest_feasibility_status, latest_strategy_status, created_at}]`. Each `latest_*_status` is `"none"` | `"draft"` | `"approved"` | `"rejected"`, derived from the most recently *created* record of that kind for the requirement (`AIAnalysis`/`FeasibilityStudy`/`TestStrategy` respectively; ties broken by an internal DB-generated monotonic sequence, not by `created_at` alone — see `.sequence` on each model in `app/domains/requirements/models.py`).
- `GET /projects/{id}/requirements/{req_id}` → 200 full requirement, which (Sprint 3) also includes `latest_feasibility_status`/`latest_strategy_status` (same semantics as above) - 404 if not found or not a member (never leaks existence). Note: unlike the list endpoint, this endpoint does *not* include `latest_analysis_status` - that was Sprint 2's own scope choice for the list endpoint only, left as-is; Sprint 3 only added the two fields the spec asked for here.
- `PATCH /projects/{id}/requirements/{req_id}` — any subset of `{title, description, business_objective, acceptance_criteria, priority}` → 200 updated (same `latest_feasibility_status`/`latest_strategy_status` fields as the detail response above).
- `DELETE /projects/{id}/requirements/{req_id}` — admin only → 204.

**AI Analysis** (nested under a requirement; `member`/`admin` can trigger/edit/approve/reject, `viewer` can read)
- `POST /projects/{id}/requirements/{req_id}/analyses` — no body; runs `MockAIProvider.analyze_requirement` and creates a new `status="draft"` analysis → 201 full detail (incl. `payload`). Does **not** touch/invalidate any prior analysis on the same requirement — every trigger adds to history.
- `GET /projects/{id}/requirements/{req_id}/analyses` → 200 list, newest first. **List items omit `payload`** (only `id, requirement_id, status, created_by, created_at, approved_by, approved_at, updated_at`) to keep the list response small; use the detail endpoint for the full payload.
- `GET /projects/{id}/requirements/{req_id}/analyses/{analysis_id}` → 200 full detail incl. `payload`.
- `PATCH /projects/{id}/requirements/{req_id}/analyses/{analysis_id}` — `{payload: <RequirementAnalysisPayload>}` → 200 updated. Only while `status == "draft"`; 409 otherwise. This is how a human edits the AI's draft output before approving.
- `POST .../analyses/{analysis_id}/approve` — sets `status="approved"`, `approved_by`, `approved_at`. Only from `status == "draft"`; 409 otherwise.
- `POST .../analyses/{analysis_id}/reject` — sets `status="rejected"`. Only from `status == "draft"`; 409 otherwise.

The `RequirementAnalysisPayload` shape (`app/domains/ai/schemas.py`): `summary` (str),
`business_rules` / `functional_conditions` / `edge_cases` / `automation_candidates` /
`manual_candidates` (lists of `{statement, rationale}`), `risks` (list of
`{statement, rationale, severity: low|medium|high}`), `ambiguities` (list of
`{statement, clarifying_question}`), `missing_information` (list of str).

**Feasibility Study** (Sprint 3; nested under a requirement, same role rules as
Analysis: `member`/`admin` trigger/edit/approve/reject, `viewer` reads) — identical
shape/lifecycle to AI Analysis, at `/projects/{id}/requirements/{req_id}/feasibility`
(and `/feasibility/{feasibility_id}`, `/feasibility/{feasibility_id}/approve`,
`/feasibility/{feasibility_id}/reject`), backed by `MockAIProvider.feasibility_study`
and the `FeasibilityStudyPayload` shape: `summary` (str), `scenarios` (list of
`{title, description, recommendation: automate|manual|hybrid|needs_review, reason,
overridden_recommendation}`). `overridden_recommendation` starts `null` and is how a
human reviewer records their own call on a scenario via `PATCH` *without* overwriting
the AI's original `recommendation` - both stay visible side by side.

**Test Strategy** (Sprint 3; same nesting/role rules, path segment `strategy`) — same
shape/lifecycle again, at `/projects/{id}/requirements/{req_id}/strategy`, backed by
`MockAIProvider.generate_test_strategy` and the `TestStrategyPayload` shape: `summary`
(str), `levels` (list of `{level: functional|api|ui|integration|security|performance|regression,
applicable: bool, estimated_scenario_count: int, notes}`), `environments` /
`test_data_requirements` / `dependencies` (lists of str), `automation_scope_notes` /
`manual_scope_notes` (str). Generating a test strategy is **not** blocked on an
approved feasibility study existing: if one does, its payload is passed to the
provider as extra context (referenced in the generated summary/scope notes); if none
exists, generation proceeds anyway with `None` in its place.

## Deviations from the original spec

- **Last-admin protection is general, not just self-demotion.** The spec's example
  was "prevent a project's last remaining admin from demoting themselves." The
  implementation blocks removing the *last* admin's admin status (via role change
  or removal) regardless of whether they're acting on themselves or another admin
  demotes/removes them — otherwise a two-admin project could still be dropped to
  zero admins by one admin demoting/removing the other. This is a strict superset
  of the required behavior.
- **(Sprint 2) `AIAnalysis` carries an internal `sequence` column** (a Postgres
  `GENERATED ALWAYS AS IDENTITY` bigint, never exposed via the API) used to determine
  "most recently created analysis" instead of `created_at`. Two analyses triggered in
  quick succession can land on the same `created_at` value (timestamp resolution),
  which made `latest_analysis_status` and the analyses list's "newest first" order
  non-deterministic when ordering by `created_at` alone; `sequence` is guaranteed
  monotonically increasing in insertion order and fixes that.
- **(Sprint 2) `PATCH` on requirements/analyses cannot explicitly null out a nullable
  field**, matching the existing `PATCH /projects/{id}` convention (`ProjectUpdate`):
  an omitted field and an explicit `null` are both treated as "leave unchanged."
  Nullable fields (`business_objective`, `acceptance_criteria`) can only be set to a
  value, not cleared back to `null`, via this endpoint.
- **(Sprint 3) `FeasibilityStudy`/`TestStrategy` each carry their own internal
  `sequence` column**, same trick and same reason as `AIAnalysis.sequence` (Sprint
  2's fix - see above). Two independent `IDENTITY` sequences (one per table), not a
  shared one, since "latest across kinds" is never a query this app needs to make.
- **(Sprint 3) `latest_feasibility_status`/`latest_strategy_status` were added to the
  single-requirement `GET`/`PATCH`/`POST` responses, but `latest_analysis_status` was
  not.** The spec asked for exactly this (mirror the list endpoint's `latest_analysis_status`
  computation, but only add the two new fields to the detail responses), so the
  detail response is intentionally asymmetric with the list response here - list has
  all three, detail has two. Not fixed unilaterally since Sprint 2's analyses
  endpoints/response shape were explicitly off-limits to modify this sprint.
- **(Sprint 3) `FeasibilityScenario.overridden_recommendation` is never mutated by the
  server** - `POST .../feasibility` always creates scenarios with it `null` (equal to
  "no override yet"); a human sets it via `PATCH` by sending back the whole edited
  payload, same edit-while-draft mechanism Sprint 2 established for `AIAnalysis`.
- Everything else follows the spec's API contract and architecture as written.

## Known pre-existing issue found during Sprint 3 verification (not fixed - out of scope)

While verifying the new migration's downgrade/upgrade round trip, a full
`alembic downgrade base` followed by `alembic upgrade head` was also tried (beyond
what the task required) and failed with `type "project_role" already exists`. This is
because Sprint 1's initial migration (`e135be9b9778`) drops the `projects`/
`project_members` tables in `downgrade()` but never drops the Postgres ENUM types
backing them (`project_role`, and likely others) - the same class of bug Sprint 2
fixed for its own migration's enums, and this sprint fixed for its own
(`feasibility_status`/`strategy_status`). Sprint 1's migration was left untouched per
this sprint's explicit "don't modify identity/projects" instruction; a full
`downgrade base` was never exercised by either prior sprint's own verification, so
this pre-existing gap was previously latent. **This sprint's own migration
(`da6737a9255c`) was verified clean for the round trip that matters** (`downgrade -1`
then `upgrade head`, straight after `upgrade head`), which is what Sprint 3's task
required.
