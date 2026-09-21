"""Rubric scoring for review reports.

Every dimension starts at 5.0 and is penalised by the issues reported for that
dimension. Penalties deliberately taper: one critical finding is worse than five
cosmetic notes, so the *first* finding at a given severity in a dimension costs more
than the follow-ups.

The model is intentionally simple and deterministic (no ML, no hidden state) so that
scores are auditable: given a report, anyone can reproduce the math by hand.
"""

from __future__ import annotations

from .models import (
    DIMENSIONS,
    DIMENSION_LABELS,
    Issue,
    ReviewReport,
    Severity,
    SEVERITY_RANK,
)

FLOOR_SCORE = 1.0

FIRST_HIT_PENALTY = {
    Severity.CRITICAL: 1.8,
    Severity.HIGH: 1.2,
    Severity.MEDIUM: 0.8,
    Severity.LOW: 0.4,
    Severity.INFO: 0.2,
}

FOLLOWUP_PENALTY = {
    Severity.CRITICAL: 0.9,
    Severity.HIGH: 0.6,
    Severity.MEDIUM: 0.4,
    Severity.LOW: 0.2,
    Severity.INFO: 0.1,
}

VERDICTS = (
    (4.5, "Ready: strong candidate for production training data"),
    (3.5, "Reviewable: address critical/high findings before use"),
    (0.0, "Needs rework: must be rewritten before it can train or evaluate anything"),
)


def _penalty(issues: list[Issue]) -> float:
    first_seen: set[Severity] = set()
    penalty = 0.0
    for issue in sorted(issues, key=lambda i: SEVERITY_RANK[i.severity]):
        if issue.severity in first_seen:
            penalty += FOLLOWUP_PENALTY[issue.severity]
        else:
            penalty += FIRST_HIT_PENALTY[issue.severity]
            first_seen.add(issue.severity)
    return penalty


def compute_dimension_scores(issues: list[Issue]) -> list:
    from .models import DimensionScore

    by_dimension: dict[str, list[Issue]] = {dim: [] for dim in DIMENSIONS}
    for issue in issues:
        bucket = by_dimension.setdefault(issue.category, [])
        bucket.append(issue)

    scores = []
    for dimension in DIMENSIONS:
        dimension_issues = by_dimension[dimension]
        if not dimension_issues:
            scores.append(DimensionScore(dimension, 5.0, "no findings"))
            continue
        penalty = _penalty(dimension_issues)
        score = max(FLOOR_SCORE, round(5.0 - penalty, 1))
        top = dimension_issues[0].severity.value
        rationale = (
            f"{len(dimension_issues)} finding(s); top severity: {top}"
        )
        scores.append(DimensionScore(dimension, score, rationale))
    return scores


def _verdict(overall: float) -> str:
    for threshold, label in VERDICTS:
        if overall >= threshold:
            return label
    return VERDICTS[-1][1]


def summarize(report: ReviewReport) -> str:
    """Produce a one-line verdict plus the top three findings."""
    if not report.issues:
        return "No findings. Scenario is clean under the registered rule set."
    counts = report.counts_by_severity()
    top = ", ".join(
        f"{n} {sev}"
        for sev, n in (("critical", counts["critical"]), ("high", counts["high"]))
        if n
    ) or f"{counts['medium']} medium"
    message = (
        f"Score: {report.overall_score:.1f}/5 -> {_verdict(report.overall_score)} "
        f"({len(report.issues)} findings: {top})"
    )
    worst = report.sorted_issues()[:3]
    if worst:
        message += " | Top: " + "; ".join(f"{i.rule_id} {i.message}" for i in worst)
    return message