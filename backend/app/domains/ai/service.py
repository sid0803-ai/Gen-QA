"""AIService: the single place that decides which AIProvider implementation
handles requirement analysis. `MockAIProvider` is the only/default provider
for now (Sprint 2); a real LLM-backed provider can be swapped in here later
without any caller (`app.domains.requirements.service`) needing to change.
"""
from typing import Literal

from app.domains.ai.provider import AIProvider, MockAIProvider
from app.domains.ai.schemas import (
    FeasibilityStudyPayload,
    RequirementAnalysisPayload,
    RequirementInput,
    TestDesignPayload,
    TestStrategyPayload,
)


class AIService:
    def __init__(self, provider: AIProvider | None = None) -> None:
        self._provider = provider or MockAIProvider()

    def analyze_requirement(self, requirement: RequirementInput) -> RequirementAnalysisPayload:
        result = self._provider.analyze_requirement(requirement)
        # Re-validate even though MockAIProvider already returns a
        # RequirementAnalysisPayload, so a future provider that returns a
        # plain dict (e.g. parsed straight from an LLM response) is
        # guaranteed to come back validated from here too.
        return RequirementAnalysisPayload.model_validate(result)

    def feasibility_study(self, requirement: RequirementInput) -> FeasibilityStudyPayload:
        result = self._provider.feasibility_study(requirement)
        return FeasibilityStudyPayload.model_validate(result)

    def generate_test_strategy(
        self, requirement: RequirementInput, feasibility: FeasibilityStudyPayload | None = None
    ) -> TestStrategyPayload:
        result = self._provider.generate_test_strategy(requirement, feasibility)
        return TestStrategyPayload.model_validate(result)

    def generate_test_design(
        self,
        requirement: RequirementInput,
        strategy: TestStrategyPayload | None = None,
        scope: Literal["api", "ui", "both"] = "both",
    ) -> TestDesignPayload:
        result = self._provider.generate_test_design(requirement, strategy, scope)
        return TestDesignPayload.model_validate(result)
