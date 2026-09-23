# Gen-QA Frontend

Frontend for Gen-QA. Vite + React + TypeScript, Ant Design for UI, TanStack Query for
server state, Zustand for local auth/UI state, react-router-dom for routing.

## What's built

**Sprint 1 "Foundation":**

- **Auth**: register, login, logout, token refresh-on-401, protected routing.
- **Projects**: list, create, select (persisted, drives the top-bar project switcher),
  and a real Members page (`/projects/:projectId/settings/members`) — add/remove members
  and change roles, admin-only, with a friendly read-only view for non-admins.
- **Dashboard** (`/projects/:projectId`): zero/empty-state stat tiles.
- **Full product nav shell**: Requirements, Test Design, Test Cases, Test Plans,
  Automation, Testing, Schedules, Reports are all wired into the sidebar and routing.

**Sprint 2 "Requirement Center + AI Analysis review":**

- **Requirements** (`/projects/:projectId/requirements`): list (title, priority, latest
  analysis status, created date) with a "New Requirement" modal form, gated to
  member/admin. Empty state for a fresh project.
- **Requirement detail** (`/projects/:projectId/requirements/:requirementId`): full
  description/business objective/acceptance criteria, an "Edit" modal (member/admin),
  and a "Delete" action (admin only).
- **AI Analysis review**: "Analyze" triggers a new draft analysis. The draft renders as
  grouped, legible sections (Summary, Business Rules, Functional Conditions, Risks,
  Ambiguities, Missing Information, Edge Cases, Automation/Manual Candidates) — each
  rationale item shows its statement plus a secondary-styled "why" line. While a draft,
  member/admin can inline-edit every field (add/remove list items too), save, then
  Approve or Reject. Once approved/rejected the panel renders read-only. Prior analyses
  for the same requirement appear below as a lazy-loaded, read-only history list.
- The generic "status badge + save/approve/reject" chrome lives in
  `src/components/ApprovalPanel.tsx`, deliberately payload-agnostic so later sprints
  (feasibility, strategy, scenarios) can reuse it for their own draft/approve/reject flows.
- Test Design, Test Cases, Test Plans, Automation, Testing, Schedules, and Reports still
  render a "Coming soon" placeholder — no functionality yet, by design.

**Sprint 5 "Environments + Automation Script + Executions":**

- **Environments** (`/projects/:projectId/settings/environments`, a new Settings tab):
  a simple table (name, base URL, variable count) with create/edit (member/admin) and
  delete (admin-only, confirm) via a modal — name, base URL, and a key-value list editor
  (`src/components/KeyValueListEditor.tsx`) for `variables`. Needed before anything can
  execute — the Automation Script and Executions sections both key off the project's
  environment list.
- **Automation Script** section on the Test Case detail page: "Generate Script" (with an
  environment picker used as generation context) creates or regenerates a Playwright
  script; the current version's code renders in a plain monospace `Input.TextArea`
  (deliberately not a full code-editor library this sprint — keeps bundle size/scope
  down), editable by member/admin, with "Save" (PATCH — resets status to draft) and
  "Approve" (draft only) actions plus a status badge. A lazy-loaded Version History list
  shows version number, AI/Human source tag, author, and date. If the project has no
  environments yet, an inline hint points at Project Settings > Environments.
- **Executions** section, below Automation Script: a shared environment picker; a manual
  recording mini-form (status/actual result/comments -> "Record Result"); a "Run" button
  for a real automated execution, enabled only once the test case has an *approved*
  script and an environment is selected (disabled with a tooltip otherwise) — triggering
  it polls the execution every ~2s (via TanStack Query's `refetchInterval`, stopping once
  the status is terminal) and shows a live spinner/status badge. An execution history
  table below shows every past execution for this test case, expandable per-row for
  `actual_result`/`comments` (manual) or `logs`/`error_message` (automated).
- **`/projects/:projectId/automation`** (replaces the old stub): project-wide read-mostly
  table of every test case's automation script status ("None"/Draft/Approved) and last
  execution status/date, with automation-candidate/script-status filters.
- **`/projects/:projectId/testing`** (replaces the old stub): project-wide execution
  history across all test cases, with status/type/environment filters wired to
  `useSearchParams` (deep-linkable), same pattern as the Test Cases list filters.
- `StatusBadge` extended with `running` and `error` (draft/approved/passed/failed/
  blocked/skipped/pending already existed from prior sprints' vocabulary).

## Prerequisites

- Node.js 20+ and npm (or Docker, see below).
- A running Gen-QA backend implementing the API contract at `VITE_API_BASE_URL`
  (default `http://localhost:8000/api/v1`). This frontend was built against that
  contract without access to the backend implementation, so double check base URL
  and payload shapes if you see request failures.

## Running locally (without Docker)

```bash
cd frontend
cp .env.example .env   # only needed if your backend isn't at the default URL
npm install
npm run dev
```

The app runs at http://localhost:5173.

## Running via Docker Compose

From the repo root:

```bash
docker compose up frontend
```

`docker-compose.yml` (repo root) builds this folder, sets `VITE_API_BASE_URL` to
`http://localhost:8000/api/v1`, bind-mounts `./frontend` into the container, and runs
`npm run dev -- --host 0.0.0.0` on port 5173. Bring up `postgres`, `redis`, and `backend`
alongside it (`docker compose up`) for a full local stack.

## Environment variables

| Variable              | Default (see `.env.example`)     | Purpose                                   |
| ---------------------- | --------------------------------- | ------------------------------------------ |
| `VITE_API_BASE_URL`    | `http://localhost:8000/api/v1`    | Base URL for all backend API requests.     |

## Project structure

```
src/
  api/            typed fetch client + endpoint functions (auth.ts, projects.ts,
                   requirements.ts, environments.ts, automationScript.ts, executions.ts, ...)
                   + shared types + priority.ts (Select options)
  auth/           useAuth() hook, AuthProvider (bootstraps session on load), ProtectedRoute
  store/          zustand authStore: tokens, current user, selected project id
  hooks/          React Query hooks (useProjects, useProjectMembers, useRequirements,
                   useAnalyses, useEnvironments, useAutomationScript, useExecutions, ...)
  layout/         AppLayout (Ant Design Layout), Sidebar (nav), TopBar (project switcher + user menu)
  components/     StatTile, StatusBadge, ComingSoonPage, ApprovalPanel (generic
                   draft/approve/reject chrome — reusable by later sprints),
                   KeyValueListEditor (Environment `variables` editor)
  pages/
    auth/         LoginPage, RegisterPage
    projects/     ProjectsListPage, ProjectDashboardPage, ProjectSettingsLayout,
                   ProjectMembersPage, ProjectGeneralSettingsPage, ProjectEnvironmentsPage
    requirements/ RequirementsListPage, RequirementDetailPage, AnalysisPayloadView
                   (renders/edits the structured analysis payload), RequirementFormFields
    testcases/    TestCasesListPage, TestCaseDetailPage, AutomationScriptSection,
                   ExecutionsSection
    automation/   AutomationListPage (project-wide automation overview)
    testing/      ExecutionHistoryPage (project-wide execution history)
    stubs/        "Coming soon" placeholder pages for the rest of the product nav
                   (Test Plans, Schedules, Reports)
```

## Manual verification checklist

Exercised end-to-end against a stub/mock server matching the API contract (see
"Deviations / notes" below for what wasn't verified against the real backend):

1. `npm install && npm run dev` boots the app at :5173, redirects `/` to `/login` when
   logged out.
2. Register a new account -> auto-logs in -> lands on `/projects`.
3. Log out, log back in with the same credentials.
4. Create a project via "New Project" modal -> appears in the table immediately
   (query invalidation refetches the list).
5. Click a project row -> navigates to `/projects/:id`, dashboard shows all-zero /
   "No data yet" stat tiles, sidebar highlights "Dashboard".
6. Top-bar project selector lists all of the user's projects and switching projects
   updates the URL and keeps you on the same sub-page (e.g. switching while on
   Requirements stays on Requirements for the new project).
7. Every remaining sidebar nav item (Test Design, Test Cases, Test Plans, Automation,
   Testing, Schedules, Reports) renders its "Coming soon — Phase N" page inside the
   same shell.
8. `/projects/:id/settings/members` as the project creator (admin): can add a member
   by email + role, change a member's role inline, and remove a member (not self).
9. Same page as a non-admin (member/viewer) role: Add/remove/role-change controls are
   hidden, an info banner explains why, and the member list itself still loads (no
   403 surfaced to the user).
10. Simulated a 401 from a mocked API (expired access token): client calls
    `/auth/refresh` once, retries the original request transparently; when refresh
    also fails, the user is redirected to `/login`.
11. `/projects/:id/requirements` as admin: empty state, then "New Requirement" modal
    creates a requirement and navigates straight to its detail page; back on the list
    it shows priority and an analysis status of "No analysis".
12. On the detail page: "Analyze" creates a draft analysis that renders as grouped
    sections (Summary, Business Rules, Functional Conditions, Risks, Ambiguities,
    Missing Information, Edge Cases, Automation/Manual Candidates), each item showing
    its statement plus a secondary "why" rationale line. Editing a field enables "Save
    changes"; after saving, Approve flips the status to "Approved" and the panel
    becomes read-only; the requirement list's analysis badge updates to match without
    a manual refresh.
13. Running "Analyze" again on the same requirement moves the previous analysis into a
    collapsed, lazy-loaded "Analysis History" list below (read-only; payload fetched
    only on expand) while the new draft becomes current.
14. As a viewer on the same project: "New Requirement", "Edit", "Delete", and "Analyze"
    are all hidden; the requirement and its latest analysis are still fully visible,
    read-only.
15. `/projects/:id/settings/environments`: create an environment (name, base URL, a
    key-value variable), edit it, and (as admin) delete it with a confirm prompt; as a
    viewer, all of that is hidden and only a read-only table shows.
16. On a Test Case's detail page: "Generate Script" (environment picker as context)
    produces a draft script whose code renders in the textarea; editing it enables
    "Save" (status stays/returns to Draft); "Approve" flips the status badge to
    Approved and hides itself; a "Version History" collapse lazily lists v1 (AI) and
    v2 (Human, after the edit) with author/date.
17. In Executions: pick the environment, record a manual result (e.g. Passed) -> it
    appears immediately in the history table; click "Run" (enabled only once the
    script is Approved and an environment is picked) -> a live spinner + "Pending" ->
    "Running" -> terminal badge sequence plays out via polling, and the finished
    execution appears in the history table without a manual refresh.
18. `/projects/:id/automation` lists the test case with its script status (Approved)
    and last execution status/date; `/projects/:id/testing` lists both executions
    (manual + automated), and filtering by Type=Automated narrows to one row and
    updates the URL query string.

## Known deviations / simplifications (V1)

- **Token storage**: access + refresh tokens are persisted to `localStorage` (via
  zustand's `persist` middleware) for simplicity. This is explicitly called out as a
  V1 simplification, not a security-final decision — tokens in `localStorage` are
  readable by any script on the page (XSS exposure). A later sprint should move to
  httpOnly cookies or in-memory tokens with silent refresh.
- **Role source for the Members page's admin check**: the contract's
  `GET /projects/{id}/members` response doesn't include the current user's own role,
  only each member's. The frontend derives "am I admin here" from the `role` field
  already present on each entry in `GET /projects` (the list endpoint explicitly
  returns "current user's role in that project"). No new endpoint was invented —
  this only reuses data the contract already defines.
- **Phase numbers** on the stub pages (e.g. "Coming soon — Phase 2") are illustrative
  placeholders for later sprints, not a committed roadmap.
- **Role source for the Requirements/AI Analysis gating** follows the exact same
  pattern as the Members page: `myRole` is read off the matching entry in
  `GET /projects`, and member/admin gates create/edit/analyze/approve/reject while
  only admin can delete a requirement.
- **Approving/rejecting a dirty draft**: if a reviewer has unsaved local edits to an
  analysis payload, Approve/Reject is short-circuited client-side with a "save first"
  warning rather than silently discarding the edits or auto-saving — the contract's
  approve/reject endpoints don't accept a payload body, so there is no way to submit
  edits and transition status in one call.
- Not yet verified against the real backend build (built in parallel, per the
  brief) — verified via manual review of the contract plus a local mock server. If
  the live backend's response shapes differ in any way from the contract (e.g. null
  vs. omitted `description`, date formats), check `src/api/types.ts` first.
- **"No automation script yet" is an expected 404**: per the contract, `GET
  .../automation-script` 404s until one is generated. `useAutomationScript` treats that
  404 as a normal "none yet" result (resolves to `null`, no error surfaced to the
  user) — but the browser's own devtools console still logs a "Failed to load
  resource: 404" line for that network response regardless of the app catching it.
  That log line is an artifact of the browser's network panel, not an application
  error; it shows up once per test case per page load until a script exists.
- **Automation overview has no bulk endpoint to call**: the contract only exposes
  automation-script status per test case, so `useAutomationScriptsByTestCase`
  (used by the project-wide Automation page) fans out one request per test case,
  sharing the same query key/cache as the test case detail page. Fine at the scale
  this sprint targets; a future sprint should ask for a bulk endpoint if the test
  case repository grows large.
- **Automation Script version history**: the contract doesn't fully pin down whether
  a `PATCH` (manual edit) bumps `current_version`'s version number or just mutates it
  in place. This frontend treats every successful generate *and* every successful
  save as producing a new version (AI-sourced for generate, Human-sourced for save),
  so the Version History list is meaningfully populated — adjust
  `src/api/automationScript.ts`/the mock server's version bookkeeping if the real
  backend's behavior differs.
- **`KeyValueListEditor`** keeps its rows in local component state rather than
  deriving them fresh from `value` on every render, specifically so a freshly-added
  row with an empty key doesn't immediately vanish (a `Record<string, string>` can't
  represent an empty-keyed row, so naively deriving rows straight from the emitted
  value would drop it the instant it's added).

## Available scripts

- `npm run dev` — start the Vite dev server.
- `npm run build` — type-check (`tsc -b`) and produce a production build.
- `npm run preview` — preview the production build locally.
- `npm run lint` — ESLint.
- `npm run typecheck` — TypeScript project check with no emit.
