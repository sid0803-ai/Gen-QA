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
    RationaleItem,
    RequirementAnalysisPayload,
    RequirementInput,
    RiskItem,
)


class AIProvider(ABC):
    @abstractmethod
    def analyze_requirement(self, requirement: RequirementInput) -> RequirementAnalysisPayload:
        """Produce a structured analysis of the given requirement."""
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
