"""Engine orchestration and end-to-end regression tests."""

from __future__ import annotations

from scenario_review.engine import ReviewEngine
from scenario_review.models import Severity
from scenario_review.rules import ALL_RULES


def test_rule_registry_populated():
    assert len(ALL_RULES) >= 25
    ids = [r.rule_id for r in ALL_RULES]
    assert len(ids) == len(set(ids)), "rule ids must be unique"


def test_clean_scenario_produces_no_critical_or_high(clean_scenario_path):
    report = ReviewEngine().run_path(clean_scenario_path)
    counts = report.counts_by_severity()
    assert counts["critical"] == 0
    assert counts["high"] == 0
    assert report.rules_run == len(ALL_RULES)
    assert report.overall_score > 3.0


def test_flawed_scenario_is_flagged(flawed_checkout_path):
    report = ReviewEngine().run_path(flawed_checkout_path)
    counts = report.counts_by_severity()
    assert counts["critical"] + counts["high"] >= 2
    rule_ids = {i.rule_id for i in report.issues}
    assert "BP-003" in rule_ids  # hardcoded secret
    assert "EC-008" in rule_ids  # missing timeout
    assert "LF-001" in rule_ids  # vague terms
    assert report.overall_score < 5.0


def test_rules_never_crash_engine(scenario_factory):
    scenario = scenario_factory(reference_solution="", expected_behavior="", constraints="")
    report = ReviewEngine().run(scenario)
    assert all(i.rule_id != "UNSPEC" or "crashed" not in i.message for i in report.issues)


def test_report_json_serializable(flawed_checkout_path):
    import json

    report = ReviewEngine().run_path(flawed_checkout_path)
    payload = json.dumps(report.to_dict())
    assert '"score"' in payload
    assert '"issues"' in payload


def test_severity_sorting(flawed_checkout_path):
    report = ReviewEngine().run_path(flawed_checkout_path)
    ordered = report.sorted_issues()
    severities = [i.severity for i in ordered]
    rank = {s: n for n, s in enumerate([Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO])}
    ladder = [rank[s] for s in severities]
    assert ladder == sorted(ladder)