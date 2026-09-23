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


# --- Test Design (Sprint 4) --------------------------------------------------
#
# `TestDesignPayload` is the JSON shape stored in `TestDesign.payload`
# (requirements domain), mirroring how `FeasibilityStudyPayload` backs
# `FeasibilityStudy.payload` and `TestStrategyPayload` backs
# `TestStrategy.payload`. Approving a TestDesign promotes every scenario
# with `include == True` into a permanent `TestCase` row (testcases
# domain) - see `app.domains.requirements.service.approve_test_design()`.


class TestDesignScenario(BaseModel):
    title: str
    category: Literal[
        "positive",
        "negative",
        "boundary",
        "edge_case",
        "business_logic",
        "validation",
        "security",
        "performance",
        "regression",
    ]
    testing_level: Literal[
        "functional", "api", "ui", "integration", "security", "performance", "regression"
    ]
    priority: Literal["low", "medium", "high", "critical"]
    severity: Literal["minor", "major", "critical", "blocker"]
    preconditions: str
    test_data: str
    steps: list[str] = Field(default_factory=list)
    expected_result: str
    business_rule: str = ""
    automation_candidate: bool
    # Human review mechanism: starts True (the AI proposes every scenario
    # for promotion) and is how a human excludes a scenario from being
    # promoted into a TestCase at approval time, by PATCHing it to False
    # before approving. See TestDesign's approve endpoint.
    include: bool = True


class TestDesignPayload(BaseModel):
    summary: str
    scope: Literal["api", "ui", "both"]
    scenarios: list[TestDesignScenario] = Field(default_factory=list)


# --- Automation script generation (Sprint 5) ---------------------------------
#
# Minimal, ai-domain-owned views of a TestCase/Environment, mirroring
# `RequirementInput`'s own decoupling rationale (see this module's docstring):
# the ai domain deliberately does not import `app.domains.testcases.models` or
# `app.domains.environments.models` - only `app.domains.automation.service`
# knows how to build these from the real ORM rows.


class TestCaseInput(BaseModel):
    title: str
    preconditions: str = ""
    steps: list[str] = Field(default_factory=list)
    expected_result: str = ""


class EnvironmentInput(BaseModel):
    base_url: str
