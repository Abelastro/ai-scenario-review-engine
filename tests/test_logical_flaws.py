"""LF-* rule tests."""

from __future__ import annotations

import pytest

from scenario_review.rules.base import ReviewContext
from scenario_review.rules.logical_flaws import (
    ContradictoryRequirementsRule,
    EmptyInputSemanticsRule,
    OffByOneBoundaryRule,
    TimezoneNaiveDateTimeRule,
    UndefinedTermsRule,
    UnverifiableCriteriaRule,
)

VAGUE_PROMPT = (
    "Implement a robust service that handles errors properly, is efficient, "
    "and follows best practices."
)


@pytest.mark.parametrize(
    "prompt,rule_cls",
    [
        (VAGUE_PROMPT, UndefinedTermsRule),
        ("Make the loader fast.", UnverifiableCriteriaRule),
    ],
)
def test_vague_specs_flagged(scenario_factory, prompt, rule_cls):
    scenario = scenario_factory(prompt=prompt)
    assert rule_cls().check(scenario, ReviewContext(scenario))


def test_clean_spec_not_flagged(scenario_factory):
    clean = (
        "Return the median of the list. For [1,2,3] return 2. "
        "For an empty list return 0. Must not raise."
    )
    scenario = scenario_factory(prompt=clean)
    context = ReviewContext(scenario)
    assert not UndefinedTermsRule().check(scenario, context)
    assert not UnverifiableCriteriaRule().check(scenario, context)


def test_contradictory_null_policy(scenario_factory):
    scenario = scenario_factory(
        prompt="Never return null from lookup().",
        expected_behavior="Return None when the key is missing; raise on invalid input.",
    )
    assert ContradictoryRequirementsRule().check(scenario, ReviewContext(scenario))


def test_off_by_one_loops(scenario_factory):
    bad = "def f(a):\n    for i in range(1, len(a)):\n        print(a[i])\n"
    scenario = scenario_factory(reference_solution=bad)
    assert OffByOneBoundaryRule().check(scenario, ReviewContext(scenario))


def test_empty_input_undefined(scenario_factory):
    scenario = scenario_factory(
        prompt="Sum the values in a list.",
        expected_behavior="Return the sum.",
        reference_solution="def s(xs):\n    total = 0\n    for x in xs:\n        total += x\n    return total\n",
    )
    assert EmptyInputSemanticsRule().check(scenario, ReviewContext(scenario))


def test_empty_input_covered_ok(scenario_factory):
    scenario = scenario_factory(
        prompt="Sum the values in a list.",
        expected_behavior="Return 0 for an empty list.",
        reference_solution="def s(xs):\n    total = 0\n    for x in xs:\n        total += x\n    return total\n",
    )
    assert not EmptyInputSemanticsRule().check(scenario, ReviewContext(scenario))


def test_naive_datetime(scenario_factory):
    scenario = scenario_factory(
        reference_solution="def stamp():\n    return datetime.now()\n"
    )
    assert TimezoneNaiveDateTimeRule().check(scenario, ReviewContext(scenario))


def test_aware_datetime_ok(scenario_factory):
    scenario = scenario_factory(
        reference_solution="def stamp():\n    return datetime.now(timezone.utc)\n"
    )
    assert not TimezoneNaiveDateTimeRule().check(scenario, ReviewContext(scenario))