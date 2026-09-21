"""The review engine: orchestrates registered rules over a scenario."""

from __future__ import annotations

from pathlib import Path

from . import __version__
from .models import Issue, Scenario, Severity
from .rules import ALL_RULES
from .rules.base import ReviewContext, ReviewRule
from .scoring import compute_dimension_scores, summarize


class ReviewEngine:
    """Runs every registered rule over a scenario and assembles a report."""

    def __init__(self, rules: list[ReviewRule] | None = None):
        self._rules = list(rules) if rules is not None else list(ALL_RULES)

    @property
    def rules(self) -> list[ReviewRule]:
        return list(self._rules)

    def run(self, scenario: Scenario):
        from .models import ReviewReport

        context = ReviewContext(scenario)
        issues: list[Issue] = []
        for rule in self._rules:
            try:
                issues.extend(rule.check(scenario, context))
            except Exception as exc:  # a buggy rule must never crash a review
                issues.append(
                    Issue(
                        rule_id=rule.rule_id,
                        category=rule.category,
                        severity=Severity.MEDIUM,
                        message=f"rule crashed while running: {exc}",
                        suggestion="fix the rule implementation and re-run",
                    )
                )

        report = ReviewReport(
            scenario=scenario,
            issues=issues,
            engine_version=__version__,
            rules_run=len(self._rules),
        )
        report.dimension_scores = compute_dimension_scores(issues)
        report.summary = summarize(report)
        return report

    def run_path(self, path: str | Path):
        return self.run(Scenario.from_yaml(path))