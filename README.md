# Gen-QA

**AI-powered QA Engineering & Test Automation Platform.**

Gen-QA takes a requirement, walks it through an AI-assisted review pipeline
(analysis → feasibility → test strategy → test design), promotes approved
scenarios into a real test case repository, generates runnable Playwright
automation scripts for them, executes those scripts for real (manually or on
a recurring schedule), and reports on the results — pass rates, coverage,
trends — all the way back up to the requirement it started from.

The guiding rule across every feature: **AI drafts, a human reviews and
approves.** Nothing an AI provider generates is ever auto-promoted into a
"real" record — every AI output lands in a `draft` state that a human edits,
approves, or rejects before it has any effect (a test case gets created, a
script gets run, etc.).

## Status

| Sprint | Scope | Status |
| --- | --- | --- |
| 1 | Foundation — auth, projects, RBAC, app shell | ✅ Done |
| 2 | Requirements + AI Analysis (draft/approve/reject) | ✅ Done |
| 3 | Feasibility Study + Test Strategy | ✅ Done |
| 4 | Test Design + Test Case Repository | ✅ Done |
| 5 | Environments + Automation Scripts + real Execution engine (Celery/Redis/Playwright) | ✅ Done |
| 6 | Reporting — dashboard, trend/breakdown reports, requirement coverage | ✅ Done |
| 7 | Scheduling — recurring automated runs (Celery Beat) | ✅ Done |
| 8 | API Performer — built-in, Postman-lite ad-hoc HTTP request tool | ✅ Done |

**New here?** [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) walks through the
whole product end to end — what each screen does and how a requirement flows
all the way to a pass/fail result on a dashboard.

Detailed, sprint-by-sprint API contracts, domain-placement decisions, and
known scope cuts live in [`backend/README.md`](backend/README.md) and
[`frontend/README.md`](frontend/README.md) — this file covers the big
picture and how to actually run the thing.

## Architecture at a glance

- **Backend**: FastAPI modular monolith. One `app/domains/<name>/` package per
  bounded context (`identity`, `projects`, `requirements`, `ai`, `testcases`,
  `environments`, `automation`, `executions`, `reporting`, …), each with its
  own `models.py` / `repository.py` / `schemas.py` / `router.py`, mounted
  under `/api/v1` in `app/main.py`. Async SQLAlchemy 2.0 + Alembic +
  PostgreSQL. Every project-scoped query enforces membership and returns a
  plain 404 (never 403) for a non-member, so project existence is never
  leaked.
- **AI layer**: an `AIProvider` abstraction (`app/domains/ai/`) behind a
  `MockAIProvider` (keyword-heuristic, no real LLM call yet) — a real
  provider can be dropped in later without touching any caller.
- **Execution engine**: real Celery + Redis. An "automated" execution enqueues
  a Celery task that runs the test case's approved Playwright script as an
  actual `npx playwright test` subprocess (via a dedicated
  `backend/automation_runner/` project) against system Chrome, and records a
  genuine pass/fail result.
- **Frontend**: Vite + React + TypeScript + Ant Design + TanStack Query
  (server state) + Zustand (auth/selected-project only). One page per
  workflow stage, a handful of reusable "AI review" chrome components
  (`ReviewSection`, `ApprovalPanel`, `StatusBadge`) shared across every
  draft/approve/reject flow.

```
Requirement → AI Analysis → Feasibility Study → Test Strategy → Test Design
                                                                      │
                                                     (approve promotes scenarios)
                                                                      ▼
                                                              Test Case Repository
                                                                      │
                                                     (generate + approve script)
                                                                      ▼
                                                            Automation Script
                                                                      │
                                                    (manual record, or real run)
                                                                      ▼
                                                                 Execution
                                                                      │
                                                                      ▼
                                                     Dashboard / Reports / Coverage
```

## Repo layout

```
backend/     FastAPI app, domains, Alembic migrations, pytest suite,
             automation_runner/ (Playwright subproject the execution engine shells out to)
frontend/    Vite + React app
docker-compose.yml   Documented container path (postgres, redis, backend, frontend)
```

## Running it locally

### Option A — Docker Compose (documented path)

```bash
cp backend/.env.example backend/.env   # only DATABASE_URL/REDIS_URL matter here; compose overrides them
docker compose up --build
```

- Backend: `http://localhost:8000/api/v1` (docs at `/docs`, health at `/health`)
- Frontend: `http://localhost:5173`

### Option B — No Docker (backend + frontend on the host)

This is the path actually used for day-to-day development in this repo (Docker
Desktop proved too slow/heavy for the dev loop here). It needs: Python 3.12,
Node 20+, a Postgres instance, and a Redis instance.

```bash
# 1. Backend deps
cd backend
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

# 2. Point at a real Postgres + Redis (any reachable instance works — a local
#    install, a container, or a pip-installable embedded one like `pgserver`
#    for zero-admin-rights dev boxes)
cp .env.example .env   # then edit DATABASE_URL / REDIS_URL if not using the defaults

# 3. Migrate + run
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# 4. Automation runner (once) — needed before any script can actually execute
cd automation_runner && npm install

# 5. Real worker, for automated executions to actually run
cd backend && celery -A app.worker worker --loglevel=info --pool=solo   # --pool=solo required on Windows

# 6. Frontend
cd frontend
cp .env.example .env   # only needed if the backend isn't at the default URL
npm install
npm run dev
```

Frontend at `http://localhost:5173`, backend at whatever port you chose
(`VITE_API_BASE_URL` in `frontend/.env` must match it).

## Running tests

```bash
cd backend
pytest              # full suite against DATABASE_URL (a *_test database is created automatically)
```

```bash
cd frontend
npm run typecheck
npm run lint
npm run build
```

`backend/tests/test_project_isolation.py` is the load-bearing suite for the
whole security model: it proves user A gets a plain 404 (never 403, never
data) on every read/write path into user B's project.

## Where to look next

- [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) — end-to-end product walkthrough:
  what Gen-QA does, roles, and the full requirement → automation → report
  workflow, screen by screen.
- [`backend/README.md`](backend/README.md) — full per-domain breakdown, API
  contract, migration/verification notes, known scope cuts and deviations,
  sprint-by-sprint.
- [`frontend/README.md`](frontend/README.md) — page-by-page feature list,
  manual verification checklist, known simplifications.
