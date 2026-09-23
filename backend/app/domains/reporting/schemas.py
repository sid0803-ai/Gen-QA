"""Pydantic schemas for the reporting domain (Sprint 6, read-only).

Every response here is a plain aggregation dict built by repository.py, not
an ORM row, so every schema is a plain `BaseModel` (no `from_attributes`
needed anywhere in this domain).
"""


from pydantic import BaseModel


class StatusBreakdown(BaseModel):
    passed: int
    failed: int
    blocked: int
    skipped: int
    error: int
    none: int


class DashboardRead(BaseModel):
    requirements_count: int
    test_cases_count: int
    automation_candidate_count: int
    automation_coverage_pct: float
    executions_total: int
    in_progress_count: int
    latest_status_breakdown: StatusBreakdown
    pass_rate_pct: float | None
    open_failures_count: int
    scheduled_jobs_count: int


class TrendPoint(BaseModel):
    date: str
    passed: int
    failed: int
    blocked: int
    skipped: int
    error: int
    total: int


class BreakdownByTestingLevel(BaseModel):
    testing_level: str
    total: int
    passed: int
    failed: int
    blocked: int
    skipped: int
    error: int
    no_runs: int


class BreakdownByCategory(BaseModel):
    category: str
    total: int
    passed: int
    failed: int
    blocked: int
    skipped: int
    error: int
    no_runs: int


class BreakdownByPriority(BaseModel):
    priority: str
    total: int
    passed: int
    failed: int
    blocked: int
    skipped: int
    error: int
    no_runs: int


class BreakdownRead(BaseModel):
    by_testing_level: list[BreakdownByTestingLevel]
    by_category: list[BreakdownByCategory]
    by_priority: list[BreakdownByPriority]


class RequirementCoverageRead(BaseModel):
    requirement_id: str
    test_case_count: int
    automated_count: int
    manual_count: int
    hybrid_count: int
    automation_script_approved_count: int
    latest_status_breakdown: StatusBreakdown
    pass_rate_pct: float | None
