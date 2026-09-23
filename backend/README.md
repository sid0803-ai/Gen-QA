# Gen-QA Backend — Sprint 1 + Sprint 2 + Sprint 3 + Sprint 4 + Sprint 5

FastAPI modular-monolith backend. Sprint 1 implemented two domains, Sprint 2 added two
more, Sprint 3 extended `requirements`/`ai` with Feasibility Study + Test Strategy,
Sprint 4 extended them again with a fourth review stage (Test Design) plus a brand-new,
project-scoped domain (Test Case Repository), and Sprint 5 is a bigger architectural
jump: it adds a lightweight Environments concept, real per-test-case Playwright/
TypeScript script generation + versioning, and an actual Celery + Redis execution
engine that runs those scripts as real subprocesses and records genuine pass/fail
results — not simulated. Every prior sprint was "AI drafts a JSONB payload, human
approves it"; Sprint 5 is the first time this backend actually *executes* anything.

- **identity** (Sprint 1) — user registration, login (OAuth2 password flow), JWT
  access/refresh tokens, `GET /auth/me`.
- **projects** (Sprint 1) — projects and project membership (roles: `admin` >
  `member` > `viewer`), with project membership as the sole data-isolation boundary.
- **requirements** (Sprint 2, extended Sprint 3, extended Sprint 4) — project-scoped
  requirements (title, description, business objective, acceptance criteria, priority)
  and four parallel AI-assisted review lifecycles hanging off each requirement, all
  sharing the same draft → approved/rejected shape (editable while draft):
  `ai_analyses` (Sprint 2), `feasibility_studies` and `test_strategies` (Sprint 3),
  `test_designs` (Sprint 4). Approving a `test_design` additionally promotes its
  included scenarios into permanent `TestCase` rows (see **testcases** below) — the
  one review stage whose approval has a side effect beyond flipping its own status.
- **ai** (Sprint 2, extended Sprint 3, extended Sprint 4) — the `AIProvider`
  abstraction + `AIService` that generates a structured payload for a requirement:
  `RequirementAnalysisPayload` (Sprint 2), `FeasibilityStudyPayload` /
  `TestStrategyPayload` (Sprint 3), `TestDesignPayload` (Sprint 4). Only a
  `MockAIProvider` (keyword-heuristic, no real LLM call) exists so far; a real
  provider can be added later without changing any caller. This domain has no
  database model of its own — `AIAnalysis`/`FeasibilityStudy`/`TestStrategy`/
  `TestDesign` (the persisted results) all live in the `requirements` domain, since
  their lifecycle (draft/approve/reject, edit-while-draft, multi-record history) is a
  requirements-domain concern, not an ai-domain one.
- **testcases** (Sprint 4, new domain) — the project-scoped Test Case Repository:
  `TestCase` (with per-test-case `TestCaseVersion` edit history) and CRUD/search over
  it. Unlike `ai_analyses`/`feasibility_studies`/`test_strategies`/`test_designs`, a
  `TestCase` is reached at the *project* level, not nested under one requirement (see
  **Sprint 4 domain-placement decision** below) — every test case still carries a
  required `requirement_id` for traceability, and optionally a `test_design_id` when
  it was AI-promoted rather than authored manually.
- **environments** (Sprint 5, new domain) — project-scoped `Environment` rows
  (`name`, `base_url`, a plain `variables` dict) that test executions run against.
  Plain CRUD, same role convention as every other domain (`viewer` reads, `member`
  creates/edits, `admin` deletes). See the **security scope cut** note below —
  `variables` is intentionally **not encrypted** this sprint.
- **automation** (Sprint 5, new domain) — one `AutomationScript` per `TestCase`
  (one-to-one), draft → approved, with a `ScriptVersion` history mirroring
  `TestCaseVersion`'s own "full snapshot per version" pattern exactly. Nested under a
  test case (`/projects/{id}/test-cases/{id}/automation-script`). `AIProvider` gained
  `generate_playwright_script()` (Sprint 5): the mock's output is a **genuinely
  runnable Playwright Test file**, not decorative text — see **the execution engine**
  below for why that matters.
- **executions** (Sprint 5, new domain) — project-scoped `Execution` records, either
  `type="manual"` (a human recording something that already happened, immediately
  `completed_at`-stamped) or `type="automated"` (enqueues a **real Celery task** that
  runs the test case's current *approved* automation script as a real
  `npx playwright test` subprocess against the given environment, and updates the row
  as it progresses: `pending` → `running` → a genuine terminal status). See **the
  execution engine** below.
- **`app/worker.py`** (Sprint 5) — the Celery application instance
  (`celery_app = Celery("genqa", broker=..., backend=...)`), reading `REDIS_URL` from
  `app.core.config.Settings` (wired since Sprint 1, unused until now). The task itself
  (`run_automated_execution`) delegates to `app.domains.executions.tasks`, which holds
  the actual execution-engine logic.
- **`backend/automation_runner/`** (Sprint 5) — a small, dedicated Playwright Test
  project (its own `package.json` + `playwright.config.ts`) that the executions
  domain's Celery task shells out to. See **the execution engine** below.

Every future domain will be added the same way:
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

**Sprint 4 domain-placement decision**: `TestDesign` followed Sprint 3's own
precedent exactly — a fourth table/model class inside `app/domains/requirements/`,
since it's still "AI suggests, human reviews, human approves" tied 1:1 to one
requirement. `TestCase`/`TestCaseVersion`, however, went into a brand-new
`app/domains/testcases/` package instead of also living in `requirements`, because
they break the pattern that justified keeping the other three inside `requirements`
in the first place: a `TestCase` is *not* only ever reached through "the Requirement
it belongs to" — it's listed/searched/filtered at the *project* level (`GET
/projects/{id}/test-cases?...`), independently of which requirement or test design
(if any) produced it, and it will keep growing its own project-scoped concerns
(search/filter, and later sprints' execution tracking) that have nothing to do with
a single requirement's review lifecycle. Mixing that into `requirements` would have
meant either a second, project-scoped repository living oddly inside a
requirement-scoped module, or bending `requirements`' repository functions (all of
which take `requirement_id` as a first-class parameter) to also support "no specific
requirement" queries. A new domain avoids both.

**Sprint 4 code-generation concurrency-safety approach**: `TestCase.code` (`"TC-001"`,
`"TC-002"`, ...) must be unique per project and sequential, and must stay that way
under concurrent creation requests. A naive `SELECT count(*) FROM test_cases WHERE
project_id = :p` + 1 is a classic race: two concurrent requests can both read the same
count before either commits its insert, and both compute the same next code. Instead,
`app/domains/testcases/repository.py::_next_code()` keeps a per-project counter row
(`test_case_counters`, one row per project) and takes a `SELECT ... FOR UPDATE` row
lock on it inside the *same* transaction as the `TestCase` insert that follows (both
happen on the same `AsyncSession` before its one `db.commit()`). Postgres blocks a
second concurrent transaction's `FOR UPDATE` on that same row until the first
transaction commits or rolls back, so two concurrent creations in the same project can
never observe/consume the same `next_value` — this is what actually rules out the
race, not just makes it less likely. The counter row is created on first use via
`INSERT ... ON CONFLICT DO NOTHING`, and Postgres serializes concurrent first-use
inserts the same way (the "loser" blocks until the "winner"'s transaction resolves),
so even the very first code generated for a project is safe under concurrency. See
`tests/test_test_cases.py::test_concurrent_test_case_creation_produces_unique_sequential_codes`
for a test that fires several concurrent `asyncio.gather`-driven creations (each on
its own independent DB connection/transaction, not the shared per-test fixture
connection) and asserts the resulting codes are unique with no gaps.

## Stack

Python 3.12, FastAPI, SQLAlchemy 2.0 (async, `asyncpg` driver), Alembic, Pydantic v2,
PyJWT + passlib[bcrypt], pytest + httpx + pytest-asyncio, **Celery 5.4 + Redis**
(Sprint 5), and a small **Node.js/Playwright Test** project (`automation_runner/`,
Sprint 5) the execution engine shells out to.

## Project layout

```
backend/
  app/
    main.py                      FastAPI app, routers mounted under /api/v1
    worker.py                    Sprint 5: Celery app instance + run_automated_execution task
    core/
      config.py                  Settings (env vars / .env)
      security.py                Password hashing, JWT encode/decode
      db.py                      Async engine/session, get_db dependency
      deps.py                    get_current_user, require_project_role(min_role)
    domains/
      identity/                  User model, auth endpoints
      projects/                  Project, ProjectMember, membership-enforced repository
      requirements/               Requirement + AIAnalysis + FeasibilityStudy +
                                    TestStrategy + TestDesign models, CRUD + all four
                                    review lifecycles
      ai/                          AIProvider ABC, MockAIProvider, AIService (Sprint 5:
                                    + generate_playwright_script())
      testcases/                   TestCase + TestCaseVersion + TestCaseCounter
                                    models, project-scoped CRUD/search repository
      environments/                 Sprint 5: Environment model, project-scoped CRUD
      automation/                    Sprint 5: AutomationScript + ScriptVersion,
                                    per-test-case script generation/edit/approve
      executions/                    Sprint 5: Execution model + repository/service,
                                    tasks.py holds the real execution engine
  automation_runner/              Sprint 5: dedicated Playwright Test project the
                                    execution engine shells out to (own package.json +
                                    playwright.config.ts; node_modules/ gitignored)
  alembic/                       Migrations
  tests/                         pytest suite (incl. test_project_isolation.py,
                                   test_feasibility.py, test_strategy.py,
                                   test_test_design.py, test_test_cases.py,
                                   test_environments.py, test_automation.py,
                                   test_executions.py)
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

## 7. Sprint 5: the execution engine (Celery + Redis + Playwright)

### Set up `automation_runner/` once

The executions domain's Celery task shells out to a dedicated Playwright Test
project at `backend/automation_runner/`. Install its dependency once:

```bash
cd backend/automation_runner
npm install
```

`playwright.config.ts` is configured to use the **system-installed Chrome**
(`channel: 'chrome'` on the `chromium` project) instead of a downloaded Chromium
build, so `npx playwright test` works without ever needing `playwright install` to
fetch large browser binaries — the same trick this project's frontend E2E
verification has relied on in every prior sprint, for the same sandbox-can't-
download-large-binaries reason. If Chrome isn't at the default Windows install
location, or `channel: 'chrome'` doesn't resolve it on your machine, point
`use.launchOptions.executablePath` at the real path instead (e.g.
`C:\Program Files\Google\Chrome\Application\chrome.exe`).

### Running tests (no real Redis needed)

`tests/conftest.py` sets `celery_app.conf.task_always_eager = True` (and
`task_eager_propagates = True`) for the whole test session. This is Celery's own
documented synchronous-execution test mode, not a shortcut around correctness: when
an automated execution is created, `run_automated_execution.delay(...)` runs the
**real task function** (real script-to-temp-file, real `npx playwright test`
subprocess, real JSON-reporter parsing) synchronously, in-process, instead of via an
actual broker round-trip. `pytest` therefore never needs a running Redis at all —
just `automation_runner/`'s `npm install` having been run once (above) and a system
Chrome being present.

`tests/test_executions.py::test_automated_execution_against_reachable_url_passes` /
`..._against_unreachable_url_fails_or_errors` are the tests that actually prove the
pass/fail signal is genuine: each spins up a trivial local `http.server` (or points
at an invalid `http://127.0.0.1:1` target), runs a *real* mock-AI-generated script
against it end-to-end, and asserts the resulting `Execution.status` is genuinely
derived from that run (`"passed"` vs `"failed"`/`"error"`) — not hardcoded. See
those tests' module docstring for why they use their own dedicated DB engine/
sessions (real commits) rather than the shared `client`/`db_session` fixture: the
Celery task (even in eager mode) opens its own separate DB connection to look up the
execution/script/environment, which cannot see data still sitting in the shared
fixture's uncommitted, SAVEPOINT-wrapped outer transaction.

### Running a real worker process (dev/deployment)

Point `REDIS_URL` (in `backend/.env`) at a real, reachable Redis, then start a
worker:

```bash
cd backend
celery -A app.worker worker --loglevel=info
```

(On Windows, add `--pool=solo` — Celery's default `prefork` pool isn't supported
there.)

### What was actually proven, and how (verification note, not a permanent script)

This sprint's own verification went a step further than eager mode, to prove the
*actual Celery/Redis wiring* works, not just the task function in isolation:

- **`pgserver`** (embedded Postgres, pip-installable, same as every prior sprint's
  backend build) provided the database.
- **`redislite`** (the pip-installable embedded Redis this task suggested first) does
  **not support Windows** (`the redislite module is not supported on the 'win32'
  platform` — confirmed by attempting the install) and could not be used.
- As a fallback that still proves a *real* Redis broker (rather than settling for
  eager-mode-only verification), a portable Windows Redis build
  (`tporadowski/redis`, a maintained Windows port, downloaded as a zip — no
  installer, no admin rights, no Docker/WSL2) provided a genuine `redis-server.exe`.
  A real `celery -A app.worker worker --loglevel=info --pool=solo` process was
  started against it, and a from-scratch script created a project/test
  case/environment (real commits, its own DB engine — no eager mode, no
  `tests/conftest.py` import), generated + approved a script, pointed an environment
  at a local `http.server`, called `create_automated_execution()`, and polled the
  `Execution` row. It genuinely flowed `pending` → `running` → `passed` through the
  real broker and a real separate worker process (confirmed in the worker's own log:
  `Task run_automated_execution[...] received` / `... succeeded in 14.0s`), with
  `duration_ms` and no `error_message` — not simulated, not eager. Everything
  downloaded/started for this (the redis-server binary, the worker process, the
  Redis server process) was torn down and deleted afterward; it is **not** part of
  this repository or its permanent dependency set (`redislite` was never
  successfully installed, so it isn't in `requirements-dev.txt` either).

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
- `GET /projects/{id}/requirements` → 200 list `[{id, title, priority, latest_analysis_status, latest_feasibility_status, latest_strategy_status, latest_test_design_status, created_at}]`. Each `latest_*_status` is `"none"` | `"draft"` | `"approved"` | `"rejected"`, derived from the most recently *created* record of that kind for the requirement (`AIAnalysis`/`FeasibilityStudy`/`TestStrategy`/`TestDesign` respectively; ties broken by an internal DB-generated monotonic sequence, not by `created_at` alone — see `.sequence` on each model in `app/domains/requirements/models.py`).
- `GET /projects/{id}/requirements/{req_id}` → 200 full requirement, which (Sprint 3, extended Sprint 4) also includes `latest_feasibility_status`/`latest_strategy_status`/`latest_test_design_status` (same semantics as above) - 404 if not found or not a member (never leaks existence). Note: unlike the list endpoint, this endpoint does *not* include `latest_analysis_status` - that was Sprint 2's own scope choice for the list endpoint only, left as-is; Sprint 3 only added the fields its own spec asked for here, and Sprint 4 followed the same "add just the new one" rule for `latest_test_design_status`.
- `PATCH /projects/{id}/requirements/{req_id}` — any subset of `{title, description, business_objective, acceptance_criteria, priority}` → 200 updated (same `latest_feasibility_status`/`latest_strategy_status`/`latest_test_design_status` fields as the detail response above).
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

**Test Design** (Sprint 4; same nesting/role rules, path segment `test-design`) —
same draft/approve/reject shape again, at
`/projects/{id}/requirements/{req_id}/test-design`, backed by
`MockAIProvider.generate_test_design` and the `TestDesignPayload` shape: `summary`
(str), `scope` (`api`|`ui`|`both`, echoing the value passed at creation), `scenarios`
(list of `{title, category, testing_level, priority, severity, preconditions,
test_data, steps: [str], expected_result, business_rule, automation_candidate,
include}`). `category` is one of `positive|negative|boundary|edge_case|
business_logic|validation|security|performance|regression`; `testing_level` one of
`functional|api|ui|integration|security|performance|regression`. `include` starts
`true` for every AI-proposed scenario and is how a human excludes a scenario from
promotion via `PATCH` before approving - it is never removed from the payload, only
toggled, so the full AI-proposed set stays visible even after some scenarios are
excluded.
- `POST /projects/{id}/requirements/{req_id}/test-design` — body `{scope:
  "api"|"ui"|"both"}` → 201 draft, same as the other three triggers otherwise.
- `GET .../test-design`, `GET .../test-design/{id}`, `PATCH .../test-design/{id}` —
  same list/detail/edit-while-draft shape as Feasibility Study/Test Strategy.
- `POST .../test-design/{id}/approve` → 200. **Side effect** (the one place this
  sprint's four review stages differ from each other): for every scenario in the
  payload where `include == true`, a permanent `TestCase` row is created in the
  project-wide Test Case Repository (`source="ai"`, `status="approved"` immediately,
  `test_design_id` set to this test design, `requirement_id` from the parent
  requirement) - approving a Test Design and promoting its included scenarios into
  TestCase rows happen in one DB transaction, so they're atomic (a failure partway
  through leaves neither committed). The response is the same shape as the other
  `GET .../test-design/{id}` detail response, plus two extra fields:
  `created_test_case_ids` (list of UUID) and `created_test_case_count` (int, always
  `== len(created_test_case_ids)`) - so a frontend can react to the newly created test
  cases without a second round-trip.
- `POST .../test-design/{id}/reject` → 200; no test cases are created.
- Generating a test design is **not** blocked on an approved test strategy existing:
  if one does, its applicable testing levels are passed to the provider as context
  (influencing which `testing_level`s the generated scenarios use); if none exists,
  generation proceeds anyway.

**Test Case Repository** (Sprint 4, new `testcases` domain; project-scoped - reached
directly under a project, **not** nested under a requirement, unlike every review
stage above) — `viewer` reads, `member` creates/edits/approves, `admin` deletes.
- `GET /projects/{id}/test-cases` — list with optional query params `requirement_id`,
  `testing_level`, `category`, `priority`, `status` (`draft`|`approved`),
  `automation_candidate` (bool), `search` (case-insensitive substring match on
  `title`) → 200 `[{id, code, title, testing_level, category, priority, severity,
  status, source, automation_candidate, execution_type, requirement_id,
  requirement_title, tags, created_at}]`. Includes the parent requirement's title (a
  join) so the UI never needs a second round-trip per row.
- `GET /projects/{id}/test-cases/{test_case_id}` → 200 full detail, adding `steps`
  (list of str), `preconditions`, `test_data`, `expected_result`, `business_rule`,
  `project_id`, `test_design_id` (null for manually-created test cases),
  `created_by`/`created_at`, `updated_by`/`updated_at`.
- `POST /projects/{id}/test-cases` — manual creation; body is every field except
  `id`/`code`/`test_design_id`/`source`/`status`/timestamps (the server sets
  `source="human"`, `status="draft"`, and generates `code` - see the
  code-generation concurrency-safety note above) → 201. `execution_type`, if omitted,
  defaults from `automation_candidate` (`true` → `"automation"`, `false` →
  `"manual"`).
- `PATCH /projects/{id}/test-cases/{test_case_id}` — any subset of the editable
  fields (everything from `POST` except `requirement_id`) → 200, and creates a new
  `TestCaseVersion` snapshot of the test case's state *after* the edit (see `GET
  .../versions` below). Same "omitted/null both mean leave unchanged" convention as
  every other `PATCH` in this codebase.
- `POST /projects/{id}/test-cases/{test_case_id}/approve` — `draft` → `approved`;
  409 if already approved. Only meaningful for manually-created (`source="human"`)
  test cases - an AI-promoted one is already `approved` from the moment it's created.
- `DELETE /projects/{id}/test-cases/{test_case_id}` — admin only → 204. There is no
  `reject`: a human who doesn't want a draft test case simply deletes it.
- `GET /projects/{id}/test-cases/{test_case_id}/versions` → 200 list of
  `{id, test_case_id, version_number, snapshot, edited_by, edited_at}`, newest first
  (`version_number` descending). `version_number` starts at 1 and increments once per
  `PATCH`; `snapshot` holds every editable field's value as of that version, so the
  ordered (oldest-to-newest) list reads as "what the test case looked like at each
  point."

**Environments** (Sprint 5, new domain; project-scoped) — `viewer` reads, `member`
creates/edits, `admin` deletes.
- `POST /projects/{id}/environments` — `{name, base_url, variables?}` → 201.
- `GET /projects/{id}/environments` → 200 list.
- `GET /projects/{id}/environments/{env_id}` → 200 detail.
- `PATCH /projects/{id}/environments/{env_id}` — any subset of `{name, base_url,
  variables}` → 200. Same "omitted/null both mean leave unchanged" convention as
  every other `PATCH` in this codebase.
- `DELETE /projects/{id}/environments/{env_id}` — admin only → 204.
- `variables` is a plain `dict[str, str]` - **not encrypted**. See **Known scope
  cuts** below.

**Automation Script** (Sprint 5, new `automation` domain; nested under a test case,
mirrors the requirement-review-stage draft/edit/approve shape) — `viewer` reads,
`member` generates/edits/approves.
- `POST /projects/{id}/test-cases/{tc_id}/automation-script` — body
  `{environment_id?}` (used only as generation context - so the script's `base_url`
  placeholder is meaningful - never persisted onto the script itself) → runs
  `MockAIProvider.generate_playwright_script` and creates a new `source="ai"`
  `ScriptVersion`, `status="draft"`. **201** the first time a script is generated for
  a test case (creates the `AutomationScript` row); **200** on every subsequent
  regeneration.
- `GET .../automation-script` → 200 `{id, test_case_id, status, current_version:
  {version_number, code, source, created_by, created_at}, created_at, updated_at}`,
  or 404 if none exists yet.
- `PATCH .../automation-script` — `{code}` → 200. A human edit: creates a new
  `source="human"` `ScriptVersion` and resets `status="draft"` - any edit (AI
  regenerate or human edit) always requires fresh approval, same "never silently
  re-approve stale content" invariant used everywhere else in this codebase.
- `POST .../automation-script/approve` → 200 `status="approved"`; 409 if already
  approved.
- `GET .../automation-script/versions` → 200 list of `{version_number, source,
  created_by, created_at}` (no `code` - use the detail endpoint's `current_version`
  for that), newest first.

The generated Playwright script is a genuinely runnable `.spec.ts` file: it
navigates to `process.env.BASE_URL ?? <environment.base_url or a placeholder>` and
asserts the page left `about:blank`, embeds each step/expected-result as a
`// TODO:` review comment (the AI can't know this application's real selectors yet),
and ends with a placeholder `body` visibility assertion. It genuinely passes when
the target is reachable and genuinely fails/errors when it isn't - see **the
execution engine** section above.

**Executions** (Sprint 5, new domain; project-scoped, references a test case + an
environment) — `viewer` reads, `member` creates. No update/delete endpoint - an
execution is an immutable record.
- `POST /projects/{id}/executions` — two shapes depending on `type`:
  - `type="manual"`: `{test_case_id, environment_id, type: "manual", status:
    "passed"|"failed"|"blocked"|"skipped", actual_result?, comments?}` → 201,
    already `completed_at`/`started_at`-stamped immediately (a human is recording
    something that already happened; `duration_ms` stays `null` - there's nothing
    real to measure). `status` is required for a manual execution and restricted to
    the four terminal values above (422 otherwise).
  - `type="automated"`: `{test_case_id, environment_id, type: "automated"}` → 201
    with `status="pending"`, and **enqueues a Celery task** that actually runs the
    test case's current *approved* automation script against the given environment.
    409 if the test case has no approved automation script yet. `status`/
    `actual_result`/`comments` must be omitted for this shape (422 otherwise - those
    are manual-only fields).
- `GET /projects/{id}/executions` — list, filters `test_case_id?`, `status?`,
  `type?`, `environment_id?`, newest first.
- `GET /projects/{id}/executions/{id}` — detail; the frontend polls this for
  automated executions until `status` leaves `pending`/`running`.

`Execution` fields: `id, project_id, test_case_id, environment_id, type, status,
triggered_by, started_at, completed_at, duration_ms, actual_result, comments, logs,
error_message, created_at`. `actual_result`/`comments` are manual-only; `logs`
(captured stdout/stderr, truncated) and `error_message` are automated-only.

## Known scope cuts (Sprint 5)

- **`Environment.variables` is stored as plain JSONB, not encrypted.** This is
  exactly the kind of field (API keys, test-account passwords) the architecture's
  own security section eventually wants encrypted-at-rest (KMS/envelope encryption,
  rotation, etc.), but building that story is out of scope for this sprint. Documented
  here explicitly as a security follow-up, not an oversight - see
  `app/domains/environments/models.py`'s module docstring.
- **No screenshot/video/trace artifact capture.** Capturing Playwright artifacts
  needs object storage (S3/MinIO), which isn't built yet. `Execution.logs`/
  `error_message` (text only, from stdout/stderr and the JSON reporter) are the whole
  result surface this sprint. A clear follow-up for a later sprint once storage
  exists.
- **No scheduling/cron** and **no reporting/dashboards** - explicitly out of scope
  per this sprint's own task description, left for later sprints.

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
- **(Sprint 4) `TestDesign` carries its own internal `sequence` column, added
  proactively rather than discovered as a bug.** Sprints 2 and 3 each added this
  column to their own new table(s) only after finding the "two rows share a
  `created_at` value" non-determinism the hard way; the task for this sprint called
  that out explicitly and asked for it to be added up front for `TestDesign`, which
  this does (same trick/reason as `AIAnalysis.sequence` - see above).
- **(Sprint 4) `TestCase.code` generation is concurrency-safe by construction, not
  by locking at the API layer.** See the code-generation concurrency-safety note
  earlier in this README and `app/domains/testcases/repository.py::_next_code()`'s
  docstring for the full reasoning; briefly, a per-project counter row locked with
  `SELECT ... FOR UPDATE` in the same transaction as the `TestCase` insert, rather
  than an application-level `count(*) + 1`.
- **(Sprint 4) `TestCaseUpdate`'s enum-typed fields accept either a plain string or
  an already-typed enum value**, normalized internally via
  `app.domains.testcases.repository._normalize_enum_fields()`. This exists because
  values flowing in from `app.domains.requirements.service.approve_test_design()`
  (promoting a `TestDesignScenario`, whose fields are plain `Literal[...]` strings
  defined in the `ai` domain) and values flowing in from `testcases.schemas` (already
  typed as this domain's own `Enum` classes) both need to reach the same ORM
  attribute-assignment code path safely.
- **(Sprint 4) `TestCase.priority` reuses the existing `requirement_priority`
  Postgres ENUM type** (the same one backing `Requirement.priority`) rather than
  defining a second, parallel priority enum - "priority" means the same thing
  everywhere in this system. This required manually adjusting the autogenerated
  migration's `CREATE TABLE test_cases` to pass `create_type=False` for that column
  (autogenerate has no way to know the type already exists) and to make sure
  `downgrade()` does **not** drop `requirement_priority` (it isn't this migration's
  type to drop - `requirements.priority` still depends on it).
- **(Sprint 5) The Celery task always runs its DB work through its own dedicated,
  short-lived engine** (`app.domains.executions.tasks._run()`), never the shared
  `app.core.db.engine`/`AsyncSessionLocal` singletons. `run_automated_execution_sync()`
  is called from two very different contexts - a real Celery worker process, and
  `task_always_eager` test mode, where `.delay()` runs the task inline from *inside*
  an already-running asyncio event loop (pytest-asyncio) - and always executes the
  task's real logic inside a brand-new thread with its own fresh `asyncio.run()` loop
  (see that function's docstring for why `asyncio.run()` can't be called directly on
  the calling thread in the eager-mode case). Reusing one shared, long-lived asyncpg
  connection pool across many different event loops (a new one per task invocation)
  would eventually hand a task a connection bound to an earlier, now-closed loop and
  crash with "Future ... attached to a different loop" - the same class of bug
  `tests/conftest.py` documents and works around for its own per-test engines: a fresh
  engine, created and disposed within the task's own single loop, sidesteps it
  entirely.
- **(Sprint 5) Version lookups in the `automation` domain always run a fresh,
  explicit `SELECT` against `ScriptVersion`**, never `AutomationScript.versions` (the
  ORM relationship collection) - see `app/domains/automation/repository.py`'s module
  docstring. Under an `AsyncSession` with `expire_on_commit=False` (as this codebase's
  test fixtures use, reusing one session across many simulated "requests"), an
  already-loaded relationship collection on an identity-mapped parent object is not
  automatically refreshed after a later commit adds more child rows through a plain
  `db.add(child)` rather than via the relationship attribute itself - a subsequent
  read of that stale collection silently missed the just-added version during this
  sprint's own test-writing (`test_patch_creates_human_version_and_resets_to_draft`
  initially failed exactly this way). `app.domains.testcases.repository
  .update_test_case()` already avoids this same trap via an explicit `COUNT` query;
  the automation domain follows that established precedent instead of the ORM
  relationship.
- **(Sprint 5) `executions.models.ExecutionKind`, not `ExecutionType`, names the
  manual/automated distinction on `Execution.type`.** `app.domains.testcases.models`
  already defines an `ExecutionType` enum (`manual|automation|hybrid`) for a
  *different* concept - a test case's intended execution mode - and reusing that name
  for "what kind of execution record is this" would have been confusing alongside it,
  so Sprint 5 introduces a distinctly-named enum instead.
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
required. **Sprint 4's own migration (`5593e511c60c`) was verified the same way**
(`upgrade head` → `downgrade -1` → `upgrade head`, all clean) against a real Postgres
instance (`pgserver`, embedded, no Docker/WSL2 available in that sandbox).
**Sprint 5's own migration (`57e6f76344ad`) was verified the same way**
(`upgrade head` → `downgrade -1` → `upgrade head`, all clean), also against a real
`pgserver` instance, with `downgrade()` explicitly dropping this migration's four new
Postgres ENUM types (`automation_script_status`, `execution_kind`, `execution_status`,
`script_source`).
