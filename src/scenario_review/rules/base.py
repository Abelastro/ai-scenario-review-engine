"""Rule interface shared by all checks."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..models import Issue, Scenario, Severity


@dataclass
class ReviewContext:
    """Pre-computed views of the scenario that rules can lean on."""

    scenario: Scenario

    @property
    def spec(self) -> str:
        """Prompt + expected behavior + constraints (the 'what should happen')."""
        return "\n".join(
            filter(
                None,
                [
                    self.scenario.prompt,
                    self.scenario.expected_behavior,
                    self.scenario.constraints,
                ],
            )
        )

    @property
    def code(self) -> str:
        """The reference solution (the 'how it was written')."""
        return self.scenario.reference_solution

    def all_text(self) -> str:
        return "\n".join([self.spec, self.code])


class ReviewRule(ABC):
    """Base class for all review checks.

    Subclasses declare static metadata (``rule_id``, ``name``, ``category``,
    ``default_severity``) and implement :meth:`check`, returning zero or more
    :class:`Issue` objects. Rules are symptom-based heuristics: they flag patterns
    worth a human review, always with evidence and a concrete suggestion.
    """

    rule_id: str = "UNSPEC"
    name: str = "UnspecifiedRule"
    category: str = "correctness"
    default_severity: Severity = Severity.MEDIUM
    description: str = ""

    @abstractmethod
    def check(self, scenario: Scenario, context: ReviewContext) -> list[Issue]:
        raise NotImplementedError

    def issue(
        self,
        message: str,
        evidence: str = "",
        suggestion: str = "",
        severity: Severity | None = None,
    ) -> Issue:
        return Issue(
            rule_id=self.rule_id,
            category=self.category,
            severity=severity or self.default_severity,
            message=message,
            evidence=evidence,
            suggestion=suggestion,
        )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.rule_id} [{self.category}]>"