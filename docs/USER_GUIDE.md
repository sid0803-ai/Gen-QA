# Gen-QA — End-to-End User Guide

This document explains **what Gen-QA does and how to use it, start to finish**
— from creating an account to reading a pass-rate trend on the dashboard. For
API contracts, database schema, and implementation notes, see
[`backend/README.md`](../backend/README.md) and
[`frontend/README.md`](../frontend/README.md). For how to *run* the app
locally, see the root [`README.md`](../README.md).

---

## 1. What Gen-QA is

Gen-QA turns a plain-English requirement into a tested, automated, and
continuously-monitored piece of your product's quality process. One
requirement flows through a single pipeline:

```
Requirement
   │
   ├─► AI Analysis            (what does this requirement actually mean?)
   ├─► Feasibility Study      (can/should each scenario be automated?)
   ├─► Test Strategy          (which testing levels apply — UI, API, security, …?)
   └─► Test Design            (concrete test scenarios)
              │
              │  (approve → promotes selected scenarios)
              ▼
        Test Case Repository
              │
              │  (generate + approve a script)
              ▼
        Automation Script (Playwright)
              │
       ┌──────┴───────┐
       ▼              ▼
  Run it now      Run it on a schedule
       │              │
       └──────┬───────┘
              ▼
          Execution (pass/fail/blocked/…)
              │
              ▼
   Dashboard · Reports · Requirement Coverage
```

**The one rule that shapes everything**: at every AI-assisted step, the AI
produces a **draft**. Nothing it drafts has any effect on your project until
a human reviews it and clicks **Approve**. You can always edit a draft before
approving it, and every approval/rejection is permanent — if you want to try
again, you generate a new draft (the old one stays in history).

---

## 2. What you need

- **An account** — self-service registration, no admin approval needed.
- **A project** — the top-level container for everything (requirements, test
  cases, environments, schedules, …). You're an `admin` of any project you
  create.
- **At least one environment** (a base URL) before you can generate or run
  automation scripts against something.
- Nothing else — the AI provider used today is a built-in mock (no API key,
  no external account needed); see [§9](#9-a-note-on-the-ai-provider).

---

## 3. Roles & permissions

Every project has three roles, checked on every action:

| Role | Can do |
| --- | --- |
| **viewer** | Read everything in the project. |
| **member** | Everything a viewer can, plus: create/edit requirements, trigger AI steps, create test cases, generate/edit/approve automation scripts, create environments, record manual executions, trigger automated runs, create/edit schedules. |
| **admin** | Everything a member can, plus: delete requirements/test cases/environments/schedules, manage project members and their roles, edit project settings. |

The person who creates a project is automatically its first `admin`. A
project can never be left with zero admins (the last admin can't be demoted
or removed).

If you're not a member of a project, every endpoint for it returns a plain
"not found" — Gen-QA never reveals that a project exists to someone outside
it.

---

## 4. Getting started

1. **Register** an account (email + password + full name) — you're logged in
   immediately.
2. **Create a project** — give it a name. You're now its admin.
3. *(Optional)* **Invite teammates** — Project Settings → Members → add by
   email + role. They must already have a Gen-QA account.
4. **Add an environment** — Project Settings → Environments → give it a name
   and a base URL (e.g. `https://staging.myapp.com`). You'll need at least
   one before automation scripts or executions become useful.

You're now ready to add your first requirement.

---

## 5. Step 1 — Requirements & AI Analysis

**Requirements** are where every piece of testable work starts. Go to
**Requirements → New Requirement** and describe what you're building in
plain language: title, description, business objective, acceptance criteria,
priority.

On the requirement's detail page, click **Analyze**. The AI reads your
requirement and drafts a structured breakdown:

- **Summary** — what it understood the requirement to mean.
- **Business rules** and **functional conditions** it inferred.
- **Edge cases** worth testing.
- **Automation candidates** vs **manual candidates**.
- **Risks**, each with a severity.
- **Ambiguities** — things it wasn't sure about, each with a clarifying
  question for you.
- **Missing information** it couldn't infer at all.

While the analysis is a **draft**, you can edit any field (add/remove items,
rewrite text) before deciding. Then either:

- **Approve** — locks it in; it becomes the current analysis for this
  requirement.
- **Reject** — discards this attempt.

You can run **Analyze** again at any time — the previous analysis (approved,
rejected, or an abandoned draft) is kept in a read-only history list below,
so nothing is ever lost.

---

## 6. Step 2 — Feasibility Study

Once you understand the requirement, click **Run Feasibility Study**. The AI
proposes a list of scenarios worth testing, each with a recommendation:
**automate**, **manual**, **hybrid**, or **needs review** — plus its
reasoning.

As a human reviewer, you can record your own call on any scenario
(**overridden recommendation**) without erasing the AI's original
suggestion — both stay visible side by side, so the history of "the AI
thought X, we decided Y" is preserved. Edit, then **Approve** or **Reject**,
same as Analysis.

---

## 7. Step 3 — Test Strategy

Click **Generate Test Strategy**. The AI proposes which **testing levels**
apply to this requirement — functional, API, UI, integration, security,
performance, regression — each marked applicable or not, with an estimated
scenario count and notes, plus overall notes on environments, test data
needs, dependencies, and automation/manual scope.

If you've already approved a Feasibility Study, its content is fed to the AI
as context (you'll see it referenced in the generated notes); if not, the
strategy is still generated — this step doesn't block on the previous one.

Edit and **Approve**/**Reject**, same pattern.

---

## 8. Step 4 — Test Design → Test Cases

This is the step that actually produces test cases. Click **Generate Test
Design**, choosing a scope (**API**, **UI**, or **both**). The AI proposes
concrete scenarios, each with:

- Title, category (positive/negative/boundary/edge case/business logic/
  validation/security/performance/regression), testing level, priority,
  severity
- Preconditions, test data, numbered steps, expected result
- Whether it's a good **automation candidate**
- An **include** toggle (on by default)

Review the list, uncheck **include** on anything you don't want promoted,
edit anything else you'd like changed, then **Approve**.

**Approving a Test Design has a side effect the other three steps don't
have**: every scenario still marked `include` is turned into a permanent row
in the **Test Case Repository**, ready for the next stage. (Rejecting, or
leaving a scenario unchecked, creates nothing.)

You can also skip all of the above and add a test case **directly** —
**Test Cases → New Test Case** — for anything you want to test that didn't
come from an AI-generated design. Manually-created test cases start as a
draft and need their own **Approve** click before they're considered final.

Every test case is assigned a human-readable code (`TC-001`, `TC-002`, …),
unique per project, and every edit is versioned — you can look back at
exactly what a test case looked like at any point.

---

## 9. Step 5 — Automation Scripts

Open a test case and click **Generate Script** (picking an environment gives
the AI a real base URL to target). It writes a genuinely runnable
[Playwright](https://playwright.dev/) test file — not placeholder text —
navigating to your environment's URL, with each of the test case's steps
embedded as a review comment for you to fill in with real selectors and
assertions.

The script is a **draft** until you review and **Approve** it. You can edit
the code directly in the panel; saving an edit always resets the script to
draft (so a stale, unreviewed edit is never silently treated as approved).
Every generation and every save creates a new version, visible in **Version
History**.

**Only an approved script can actually be run.**

---

## 10. Step 6 — Running tests

On the same test case, the **Executions** panel lets you:

- **Record a manual result** — pick an environment, a result (passed/
  failed/blocked/skipped), and optionally notes. This is for testing you did
  by hand; it's saved immediately as a completed record.
- **Run** the automation script for real — pick an environment and click
  **Run** (enabled only once the script is approved). This actually executes
  the Playwright script as a subprocess against that environment's URL. The
  row shows a live spinner through **Pending → Running → a real terminal
  result** (passed/failed/blocked/skipped/error), typically within seconds.

Every execution — manual or automated — appears in the history table below,
expandable to see the full result (manual: your notes; automated: logs and
any error message).

Two project-wide pages give you the same information across every test
case: **Automation** (script status + last run, per test case) and
**Testing** (every execution across the project, filterable by status/type/
environment).

---

## 11. Step 7 — Scheduling recurring runs

Once a test case's script is approved, you can put it on autopilot:
**Schedules → New Schedule**. Pick the test case (only ones with an approved
script are selectable), an environment, a name, and a
[cron expression](https://crontab.guru/) (e.g. `0 2 * * *` = every day at
2am).

From then on, Gen-QA checks every minute for schedules that are due and
fires them automatically — the same real execution engine as clicking **Run**
by hand, just triggered on a timer instead of a click. Each schedule's row
shows when it last ran and when it's due next; toggle it off any time
without deleting it, or delete it outright.

If a scheduled test case's script gets un-approved before its next run, the
schedule simply doesn't fire that tick — it isn't disabled or deleted, and
will resume firing automatically once the script is approved again.

---

## 12. Step 8 — Dashboard & Reports

**Dashboard** (a project's home page) gives you the state of the project at
a glance: requirement and test case counts, automation coverage (% of test
cases with an approved script), overall pass rate, executions in progress,
open failures, and how many schedules are active.

**Reports** goes deeper:

- **Execution trend** — a day-by-day pass/fail/blocked/skipped/error line
  chart over the last 7/30/90 days.
- **Breakdown** — pass/fail counts grouped by testing level, category, and
  priority, so you can see e.g. "our `security` category has a lower pass
  rate than `positive`."

Back on any **requirement's** detail page, a compact **coverage panel**
shows that specific requirement's own numbers: how many test cases it has,
how many are automated vs. manual vs. hybrid, how many have an approved
script, and its own pass rate — so you can trace quality all the way back to
the requirement that started it.

**How "pass rate" is calculated** (the same rule everywhere in the app): for
each test case, only its **most recent** execution counts, and only if that
execution finished (not currently pending/running, and not "never run at
all"). Pass rate = passed ÷ (passed + failed + blocked + skipped + error)
among those. A test case that's never been run, or whose latest run is still
in progress, doesn't affect the pass rate either way.

---

## 13. Status glossary

| Status | Meaning |
| --- | --- |
| `draft` | An AI-generated or human-created record awaiting review. Still editable. |
| `approved` | Reviewed and accepted. Now has downstream effect (a test design promotes test cases; a script becomes runnable). |
| `rejected` | Reviewed and declined. No downstream effect; stays in history. |
| `pending` | An automated execution has been queued but hasn't started yet. |
| `running` | An automated execution is currently executing. |
| `passed` / `failed` / `blocked` / `skipped` / `error` | Terminal execution results. `error` means the run itself broke (e.g. couldn't reach the environment); `failed` means the test ran but the assertion didn't hold. |

---

## 14. A note on the AI provider

Every "AI" step today runs against a built-in **mock provider** — a
keyword-heuristic generator, not a call to an external LLM. This means:

- No API key or external account is needed to use any part of Gen-QA.
- The drafts it produces are a reasonable structural starting point, not
  deep semantic understanding — treat every draft as exactly that, a
  starting point for a human reviewer, which is the whole point of the
  draft → approve workflow above.
- The provider sits behind a clean interface (`AIProvider`), so swapping in
  a real LLM later doesn't change how any of the workflow above works from
  a user's point of view — only the quality of what shows up in each draft.

---

## 15. Troubleshooting

- **"Test case has no approved automation script" when creating a
  schedule** — generate and approve a script for that test case first
  (§9).
- **"Run" is disabled on the Executions panel** — you need both an
  environment selected *and* an approved script for that test case.
- **Pass rate shows "No data yet"** — no test case in this project/
  requirement has a completed (terminal) execution yet; run at least one.
- **A project doesn't show up at all / 404 on a link someone sent you** —
  you're not a member of that project. Ask an admin of that project to add
  you (Project Settings → Members).
