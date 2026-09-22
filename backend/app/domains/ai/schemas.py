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
