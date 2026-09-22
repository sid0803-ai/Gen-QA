"""AIProvider abstraction.

`MockAIProvider` is the only implementation for now (Sprint 2): it derives
varied, non-empty content from the requirement's actual text using simple
keyword heuristics - no real NLP/LLM call. A real LLM-backed provider
(OpenAI/Anthropic/etc.) can be added later as another `AIProvider` subclass
without changing any caller; `app.domains.ai.service.AIService` is the only
place that decides which provider to instantiate.
"""
import re
from abc import ABC, abstractmethod

from app.domains.ai.schemas import (
    AmbiguityItem,
    FeasibilityScenario,
    FeasibilityStudyPayload,
    RationaleItem,
    RequirementAnalysisPayload,
    RequirementInput,
    RiskItem,
    TestingLevelScope,
    TestStrategyPayload,
)


class AIProvider(ABC):
    @abstractmethod
    def analyze_requirement(self, requirement: RequirementInput) -> RequirementAnalysisPayload:
        """Produce a structured analysis of the given requirement."""
        raise NotImplementedError

    @abstractmethod
    def feasibility_study(self, requirement: RequirementInput) -> FeasibilityStudyPayload:
        """Propose a set of testable scenarios with an automate/manual/hybrid/
        needs_review recommendation each."""
        raise NotImplementedError

    @abstractmethod
    def generate_test_strategy(
        self, requirement: RequirementInput, feasibility: FeasibilityStudyPayload | None
    ) -> TestStrategyPayload:
        """Propose a testing-level breakdown (+ environments/test-data/
        dependencies). `feasibility`, when provided (typically an approved
        FeasibilityStudy's payload), gives extra context to inform scope."""
        raise NotImplementedError


# (keywords, topic, severity) triples used to vary risk content by simple
# keyword presence in the requirement's combined text.
_RISK_RULES: list[tuple[list[str], str, str]] = [
    (["payment", "billing", "invoice", "credit card", "checkout", "refund"],
     "handling of financial/payment data", "high"),
    (["login", "auth", "password", "sso", "session", "token"],
     "authentication and session handling", "high"),
    (["delete", "remove", "purge", "deactivate", "cancel"],
     "irreversible or destructive data operations", "high"),
    (["admin", "role", "permission", "access control", "privilege"],
     "privilege escalation or access-control gaps", "high"),
    (["email", "sms", "notify", "notification", "alert"],
     "reliability of third-party notification delivery", "medium"),
    (["upload", "file", "attachment", "import", "document"],
     "handling of user-supplied files", "medium"),
    (["integration", "api", "webhook", "third-party", "external", "sync"],
     "dependency on an external system's availability/behavior", "medium"),
    (["report", "dashboard", "analytics", "export"],
     "accuracy of aggregated or derived data", "low"),
    (["search", "filter", "sort", "pagination"],
     "performance and correctness on large datasets", "low"),
    (["concurrent", "simultaneous", "real-time", "realtime", "parallel"],
     "race conditions under concurrent use", "medium"),
]

_AUTOMATION_KEYWORDS = [
    "api", "calculation", "compute", "validation", "validate", "workflow",
    "process", "rule", "threshold", "export", "import", "integration",
    "batch", "sync", "status", "notification",
]

_MANUAL_KEYWORDS = [
    "ui", "visual", "design", "layout", "usability", "exploratory",
    "look and feel", "accessibility", "responsive", "screen", "page",
]

_VAGUE_WORDS = [
    "fast", "quickly", "efficient", "user-friendly", "some", "several",
    "many", "appropriate", "reasonable", "etc", "as needed",
    "should probably", "might", "typically", "easy to use",
]


# (keywords, scenario title, recommendation, reason) rules used by
# MockAIProvider.feasibility_study to derive scenarios from a requirement's
# text. Order matters: earlier rules are checked first and each contributes
# at most one scenario, capped overall in feasibility_study().
_FEASIBILITY_RULES: list[tuple[list[str], str, str, str]] = [
    (["captcha", "recaptcha"],
     "CAPTCHA validation", "needs_review",
     "CAPTCHA challenges are deliberately non-deterministic and designed to resist "
     "automated interaction; whether to automate depends on an available test-mode "
     "bypass, so this needs human review before a final call is made."),
    (["third-party", "external", "webhook", "payment gateway", "sms gateway"],
     "Third-party/external system integration", "manual",
     "Behavior depends on a third-party/external system outside this application's "
     "control, which introduces non-determinism (latency, outages, sandbox drift) "
     "that makes automated assertions brittle."),
    (["email", "notify", "notification"],
     "Notification delivery", "manual",
     "Delivery of email/notification content depends on an external provider and "
     "inbox/queue timing, which is non-deterministic in an automated test run."),
    (["upload", "file", "attachment", "import", "document"],
     "File upload handling", "hybrid",
     "Combines deterministic validation logic (file type/size checks, well suited to "
     "automation) with UI/file-handling aspects that benefit from manual verification, "
     "so a hybrid approach is appropriate."),
    (["exploratory", "ux", "usability", "visual", "look and feel", "layout", "accessibility"],
     "Exploratory/UX review", "manual",
     "This aspect is subjective/visual and is better assessed through human "
     "exploratory testing than scripted assertions."),
    (["login", "registration", "sign up", "signup", "sign in", "api", "endpoint"],
     "API/functional flow", "automate",
     "This is a deterministic, rule-based flow through a stable API/UI surface, well "
     "suited to automated regression coverage."),
    (["calculation", "compute", "validation", "validate", "workflow", "process", "rule", "threshold"],
     "Business rule/calculation validation", "automate",
     "Rule-based/deterministic logic is well suited to automated checks against fixed "
     "input/output pairs."),
]


# (keywords, level) rules used by MockAIProvider.generate_test_strategy to
# decide which testing levels are applicable beyond the always-applicable
# "functional" and "regression" levels.
_LEVEL_RULES: list[tuple[list[str], str]] = [
    (["api", "endpoint", "webhook", "integration", "service", "third-party", "external", "sync"], "api"),
    (["ui", "screen", "page", "form", "button", "layout", "visual", "responsive"], "ui"),
    (["integration", "third-party", "external", "webhook", "sync", "api"], "integration"),
    (["auth", "login", "password", "sso", "session", "token", "permission", "role",
      "access control", "payment", "billing", "credit card", "checkout"], "security"),
    (["performance", "concurrent", "simultaneous", "real-time", "realtime", "parallel",
      "load", "scale", "throughput", "large"], "performance"),
]


def _combined_text(requirement: RequirementInput) -> str:
    parts = [
        requirement.title,
        requirement.description,
        requirement.business_objective or "",
        requirement.acceptance_criteria or "",
    ]
    return " ".join(parts).lower()


def _split_sentences(text: str) -> list[str]:
    sentences = [s.strip() for s in re.split(r"[.\n;]+", text) if s.strip()]
    return sentences


class MockAIProvider(AIProvider):
    def analyze_requirement(self, requirement: RequirementInput) -> RequirementAnalysisPayload:
        text = _combined_text(requirement)
        title = requirement.title.strip() or "this requirement"

        return RequirementAnalysisPayload(
            summary=self._build_summary(requirement, title),
            business_rules=self._build_business_rules(requirement, title),
            functional_conditions=self._build_functional_conditions(requirement, title),
            risks=self._build_risks(text, title),
            ambiguities=self._build_ambiguities(requirement, text, title),
            missing_information=self._build_missing_information(requirement),
            edge_cases=self._build_edge_cases(text, title),
            automation_candidates=self._build_automation_candidates(text, title),
            manual_candidates=self._build_manual_candidates(text, title),
        )

    def _build_summary(self, requirement: RequirementInput, title: str) -> str:
        word_count = len(requirement.description.split())
        detail = "a detailed" if word_count > 40 else "a brief"
        objective_clause = (
            f' It is driven by the business objective: "{requirement.business_objective.strip()}".'
            if requirement.business_objective
            else " No explicit business objective was provided, which should be clarified before development."
        )
        return (
            f"Requirement '{title}' is a {requirement.priority}-priority item described in "
            f"{detail} manner ({word_count} words).{objective_clause} This mock AI analysis "
            f"surfaces the business rules, functional conditions, risks, ambiguities and "
            f"test-design considerations a reviewer should validate before this moves forward."
        )

    def _build_business_rules(self, requirement: RequirementInput, title: str) -> list[RationaleItem]:
        items: list[RationaleItem] = []
        if requirement.acceptance_criteria:
            for sentence in _split_sentences(requirement.acceptance_criteria)[:4]:
                items.append(
                    RationaleItem(
                        statement=f"The system must satisfy: {sentence}.",
                        rationale=f"Directly derived from the stated acceptance criteria for '{title}'.",
                    )
                )
        if not items:
            items.append(
                RationaleItem(
                    statement=f"'{title}' must behave consistently with its stated priority "
                    f"({requirement.priority}) when prioritized against other work.",
                    rationale="No acceptance criteria were provided, so this rule is inferred from "
                    "the requirement's priority and description alone.",
                )
            )
        items.append(
            RationaleItem(
                statement=f"Only authorized users should be able to trigger the behavior described by '{title}'.",
                rationale="General business rule applied to every requirement pending explicit access-control detail.",
            )
        )
        return items

    def _build_functional_conditions(self, requirement: RequirementInput, title: str) -> list[RationaleItem]:
        sentences = _split_sentences(requirement.description)[:4]
        items = [
            RationaleItem(
                statement=f"System must handle: {sentence}.",
                rationale=f"Directly derived from the requirement description for '{title}'.",
            )
            for sentence in sentences
        ]
        if len(items) < 2:
            items.append(
                RationaleItem(
                    statement=f"Input to '{title}' must be validated before being processed.",
                    rationale="Generic functional condition added because the description was too short "
                    "to derive more than one condition from.",
                )
            )
        return items

    def _build_risks(self, text: str, title: str) -> list[RiskItem]:
        items: list[RiskItem] = []
        for keywords, topic, severity in _RISK_RULES:
            if any(k in text for k in keywords):
                items.append(
                    RiskItem(
                        statement=f"Risk related to {topic}.",
                        rationale=f"The text for '{title}' references terms suggesting {topic}; "
                        "this should be reviewed carefully.",
                        severity=severity,
                    )
                )
        if not items:
            items.append(
                RiskItem(
                    statement=f"Scope of '{title}' may be broader than currently described.",
                    rationale="No specific risk keywords were detected, so this is a generic "
                    "scope-ambiguity risk that should be confirmed with stakeholders.",
                    severity="low",
                )
            )
        return items[:5]

    def _build_ambiguities(
        self, requirement: RequirementInput, text: str, title: str
    ) -> list[AmbiguityItem]:
        items: list[AmbiguityItem] = []
        for word in _VAGUE_WORDS:
            if word in text:
                items.append(
                    AmbiguityItem(
                        statement=f"The requirement uses the subjective term '{word}'.",
                        clarifying_question=f"What specific, measurable criteria define '{word}' "
                        f"in the context of '{title}'?",
                    )
                )
            if len(items) >= 3:
                break
        if not items:
            items.append(
                AmbiguityItem(
                    statement=f"'{title}' does not explicitly describe behavior for invalid or unexpected input.",
                    clarifying_question="What should happen when the input to this requirement is "
                    "invalid, missing, or out of range?",
                )
            )
        return items

    def _build_missing_information(self, requirement: RequirementInput) -> list[str]:
        items: list[str] = []
        if not requirement.business_objective:
            items.append("Business objective was not provided; confirm the underlying business driver.")
        if not requirement.acceptance_criteria:
            items.append(
                "Acceptance criteria were not provided; confirm measurable pass/fail conditions."
            )
        if not items:
            items.append(
                "Non-functional requirements (performance, security, accessibility) were not "
                "explicitly addressed and should be confirmed."
            )
        return items

    def _build_edge_cases(self, text: str, title: str) -> list[RationaleItem]:
        items = [
            RationaleItem(
                statement=f"Empty, null, or missing input to '{title}'.",
                rationale="Baseline edge case applicable to virtually any requirement.",
            ),
            RationaleItem(
                statement=f"Two users triggering '{title}' concurrently for the same underlying data.",
                rationale="Concurrency edge case to catch race conditions or stale-data overwrites.",
            ),
        ]
        if any(k in text for k in ["file", "upload", "attachment", "import"]):
            items.append(
                RationaleItem(
                    statement="An oversized or malformed file is uploaded.",
                    rationale="File-handling keywords were detected in the requirement text.",
                )
            )
        if any(k in text for k in ["payment", "billing", "invoice", "checkout"]):
            items.append(
                RationaleItem(
                    statement="A payment is partially processed or times out mid-transaction.",
                    rationale="Payment-related keywords were detected in the requirement text.",
                )
            )
        if any(k in text for k in ["login", "auth", "password", "session"]):
            items.append(
                RationaleItem(
                    statement="A session expires or credentials are revoked mid-action.",
                    rationale="Authentication-related keywords were detected in the requirement text.",
                )
            )
        return items

    def _build_automation_candidates(self, text: str, title: str) -> list[RationaleItem]:
        matched = [k for k in _AUTOMATION_KEYWORDS if k in text]
        if matched:
            return [
                RationaleItem(
                    statement=f"Automate regression coverage of '{title}' around: {', '.join(matched[:3])}.",
                    rationale="These aspects are rule-based/deterministic and well suited to automated checks.",
                )
            ]
        return [
            RationaleItem(
                statement=f"Automate a smoke test verifying the primary happy path of '{title}'.",
                rationale="Even without strong automation signals, a baseline happy-path check is worth automating.",
            )
        ]

    def _build_manual_candidates(self, text: str, title: str) -> list[RationaleItem]:
        matched = [k for k in _MANUAL_KEYWORDS if k in text]
        if matched:
            return [
                RationaleItem(
                    statement=f"Manually/exploratorily review '{title}' for: {', '.join(matched[:3])}.",
                    rationale="These aspects are subjective/visual and better assessed by a human reviewer.",
                )
            ]
        return [
            RationaleItem(
                statement=f"Manually exploratory-test '{title}' for usability and unexpected interactions.",
                rationale="General recommendation to pair automation with human exploratory testing.",
            )
        ]

    # --- Feasibility Study (Sprint 3) -----------------------------------

    def feasibility_study(self, requirement: RequirementInput) -> FeasibilityStudyPayload:
        text = _combined_text(requirement)
        title = requirement.title.strip() or "this requirement"

        scenarios: list[FeasibilityScenario] = [
            FeasibilityScenario(
                title=f"{title} — happy path",
                description=f"Primary success flow through '{title}' exactly as described.",
                recommendation="automate",
                reason="Deterministic, well-defined happy-path behavior is well suited to "
                "automated regression coverage.",
            )
        ]

        if requirement.acceptance_criteria:
            for sentence in _split_sentences(requirement.acceptance_criteria)[:3]:
                scenarios.append(
                    FeasibilityScenario(
                        title=f"Verify acceptance criterion: {sentence[:60]}",
                        description=f"Validate that '{title}' satisfies: {sentence}.",
                        recommendation="automate",
                        reason="Derived directly from a stated, measurable acceptance "
                        "criterion, which is repeatable and well suited to automation.",
                    )
                )

        for keywords, scenario_title, recommendation, reason in _FEASIBILITY_RULES:
            if any(k in text for k in keywords):
                scenarios.append(
                    FeasibilityScenario(
                        title=f"{scenario_title} — {title}",
                        description=f"Assess '{scenario_title.lower()}' behavior for '{title}'.",
                        recommendation=recommendation,
                        reason=reason,
                    )
                )
            if len(scenarios) >= 7:
                break

        if len(scenarios) == 1:
            # No acceptance-criteria-derived or keyword-matched scenarios beyond
            # the always-present happy path: add a generic review scenario so a
            # feasibility study always surfaces more than a single trivial item.
            scenarios.append(
                FeasibilityScenario(
                    title=f"General scope review — {title}",
                    description=f"'{title}' did not match any strong automation/manual "
                    "signal keywords; its testable scope should be reviewed.",
                    recommendation="needs_review",
                    reason="No specific automation or manual-testing signal was detected "
                    "in the requirement text, so this should be reviewed and classified "
                    "before test design.",
                )
            )

        automate_count = sum(1 for s in scenarios if s.recommendation == "automate")
        manual_count = sum(1 for s in scenarios if s.recommendation in ("manual", "hybrid"))
        review_count = sum(1 for s in scenarios if s.recommendation == "needs_review")
        summary = (
            f"Feasibility study for '{title}' identified {len(scenarios)} testable "
            f"scenario(s): {automate_count} recommended for automation, {manual_count} "
            f"for manual/hybrid execution, and {review_count} flagged for review."
        )

        return FeasibilityStudyPayload(summary=summary, scenarios=scenarios[:7])

    # --- Test Strategy (Sprint 3) ----------------------------------------

    def generate_test_strategy(
        self, requirement: RequirementInput, feasibility: FeasibilityStudyPayload | None
    ) -> TestStrategyPayload:
        text = _combined_text(requirement)
        title = requirement.title.strip() or "this requirement"

        scenario_count = len(feasibility.scenarios) if feasibility else 0
        automatable_count = (
            sum(
                1
                for s in feasibility.scenarios
                if (s.overridden_recommendation or s.recommendation) in ("automate", "hybrid")
            )
            if feasibility
            else 0
        )
        manual_count = scenario_count - automatable_count if feasibility else 0

        applicable_levels = {level for keywords, level in _LEVEL_RULES if any(k in text for k in keywords)}

        levels: list[TestingLevelScope] = []
        functional_count = max(3, scenario_count) if scenario_count else 3
        levels.append(
            TestingLevelScope(
                level="functional",
                applicable=True,
                estimated_scenario_count=functional_count,
                notes=f"Core functional coverage of '{title}', including its primary flows "
                "and stated acceptance criteria.",
            )
        )

        for level, base_notes in [
            ("api", "Coverage of request/response contracts and error handling for any "
             "API/service endpoints involved."),
            ("ui", "Coverage of UI interactions, form validation, and visual states."),
            ("integration", "Coverage of interactions with external/third-party systems, "
             "including failure and timeout handling."),
            ("security", "Coverage of authentication, authorization, and access-control "
             "boundaries relevant to this requirement."),
            ("performance", "Coverage of load/concurrency behavior where the requirement's "
             "scope suggests it matters."),
        ]:
            applicable = level in applicable_levels
            levels.append(
                TestingLevelScope(
                    level=level,
                    applicable=applicable,
                    estimated_scenario_count=(2 if applicable else 0),
                    notes=(base_notes if applicable else f"'{title}' does not show strong "
                           f"signal for {level} testing; not currently in scope."),
                )
            )

        regression_count = max(1, automatable_count) if feasibility else 2
        levels.append(
            TestingLevelScope(
                level="regression",
                applicable=True,
                estimated_scenario_count=regression_count,
                notes="Automated scenarios from this requirement should be folded into the "
                "regression suite once approved.",
            )
        )

        environments = ["staging"]
        if "security" in applicable_levels:
            environments.append("isolated security-test environment")
        if "integration" in applicable_levels or "api" in applicable_levels:
            environments.append("sandboxed third-party/integration environment")
        if "performance" in applicable_levels:
            environments.append("performance/load-test environment")

        test_data_requirements = [
            f"Representative valid and invalid input data covering '{title}'s stated "
            "acceptance criteria."
        ]
        if "security" in applicable_levels:
            test_data_requirements.append(
                "Test accounts spanning each relevant role/permission level."
            )
        if "integration" in applicable_levels or "api" in applicable_levels:
            test_data_requirements.append(
                "Mocked/sandboxed responses for the external system(s) involved."
            )

        dependencies: list[str] = []
        if "integration" in applicable_levels or "api" in applicable_levels:
            dependencies.append(
                "Availability of a stable sandbox/mocked endpoint for the external/"
                "third-party system(s) referenced by this requirement."
            )
        if not dependencies:
            dependencies.append("No external system dependencies were detected in the requirement text.")

        if feasibility is not None:
            summary = (
                f"Test strategy for '{title}', informed by its feasibility study "
                f"({scenario_count} scenario(s): {automatable_count} automatable, "
                f"{manual_count} manual/needs-review). Levels in scope: "
                f"{', '.join(sorted(applicable_levels | {'functional', 'regression'}))}."
            )
            automation_scope_notes = (
                f"Automate the {automatable_count} scenario(s) the feasibility study "
                "recommended for automation or hybrid execution, plus baseline functional "
                "and regression coverage."
            )
            manual_scope_notes = (
                f"Manually execute the {manual_count} scenario(s) the feasibility study "
                "flagged as manual or needing review, prioritizing those with the highest "
                "risk."
            )
        else:
            summary = (
                f"Test strategy for '{title}' (no approved feasibility study available yet). "
                f"Levels in scope: {', '.join(sorted(applicable_levels | {'functional', 'regression'}))}."
            )
            automation_scope_notes = (
                "Automate deterministic, rule-based flows identified in the functional level "
                "once scenarios are defined."
            )
            manual_scope_notes = (
                "Manually cover subjective/visual and external-system-dependent behavior "
                "until a feasibility study narrows the scope further."
            )

        return TestStrategyPayload(
            summary=summary,
            levels=levels,
            environments=environments,
            test_data_requirements=test_data_requirements,
            dependencies=dependencies,
            automation_scope_notes=automation_scope_notes,
            manual_scope_notes=manual_scope_notes,
        )
