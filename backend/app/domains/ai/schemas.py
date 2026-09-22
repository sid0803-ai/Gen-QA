"""Structured schema for AI-generated requirement analysis output.

`RequirementAnalysisPayload` is the JSON shape stored in `AIAnalysis.payload`
(requirements domain) and is what any `AIProvider` implementation (mock now,
a real LLM-backed one later) must produce.

`RequirementInput` is a minimal, ai-domain-owned view of a requirement. The
ai domain deliberately does not import `app.domains.requirements.models` -
only `app.domains.requirements.service` knows how to build a
`RequirementInput` from an ORM `Requirement` row. This keeps the ai domain
decoupled, so a future real provider can be added without ever reaching into
the requirements domain's persistence layer.
"""
from typing import Literal

from pydantic import BaseModel, Field


class RequirementInput(BaseModel):
    title: str
    description: str
    business_objective: str | None = None
    acceptance_criteria: str | None = None
    priority: str = "medium"


class RationaleItem(BaseModel):
    statement: str
    rationale: str


class RiskItem(BaseModel):
    statement: str
    rationale: str
    severity: Literal["low", "medium", "high"]


class AmbiguityItem(BaseModel):
    statement: str
    clarifying_question: str


class RequirementAnalysisPayload(BaseModel):
    summary: str
    business_rules: list[RationaleItem] = Field(default_factory=list)
    functional_conditions: list[RationaleItem] = Field(default_factory=list)
    risks: list[RiskItem] = Field(default_factory=list)
    ambiguities: list[AmbiguityItem] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    edge_cases: list[RationaleItem] = Field(default_factory=list)
    automation_candidates: list[RationaleItem] = Field(default_factory=list)
    manual_candidates: list[RationaleItem] = Field(default_factory=list)


# --- Feasibility Study (Sprint 3) -------------------------------------------
#
# `FeasibilityStudyPayload` is the JSON shape stored in
# `FeasibilityStudy.payload` (requirements domain), mirroring how
# `RequirementAnalysisPayload` backs `AIAnalysis.payload`.


class FeasibilityScenario(BaseModel):
    title: str
    description: str
    recommendation: Literal["automate", "manual", "hybrid", "needs_review"]
    reason: str
    # Human override: starts as None (meaning "use `recommendation`") and is
    # set independently by a human reviewer before approval. `recommendation`
    # (the AI's original suggestion) is never overwritten, so the two stay
    # visible side by side for comparison.
    overridden_recommendation: Literal["automate", "manual", "hybrid", "needs_review"] | None = None


class FeasibilityStudyPayload(BaseModel):
    summary: str
    scenarios: list[FeasibilityScenario] = Field(default_factory=list)


# --- Test Strategy (Sprint 3) ------------------------------------------------
#
# `TestStrategyPayload` is the JSON shape stored in `TestStrategy.payload`
# (requirements domain).


class TestingLevelScope(BaseModel):
    level: Literal[
        "functional", "api", "ui", "integration", "security", "performance", "regression"
    ]
    applicable: bool
    estimated_scenario_count: int
    notes: str


class TestStrategyPayload(BaseModel):
    summary: str
    levels: list[TestingLevelScope] = Field(default_factory=list)
    environments: list[str] = Field(default_factory=list)
    test_data_requirements: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    automation_scope_notes: str
    manual_scope_notes: str
