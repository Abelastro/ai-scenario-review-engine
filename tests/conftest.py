"""Shared fixtures for the engine test suite."""

from __future__ import annotations

from pathlib import Path

import pytest

from scenario_review.models import Scenario

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "scenarios"


def make_scenario(**overrides) -> Scenario:
    defaults = {
        "id": "s",
        "title": "Test scenario",
        "stack": "python",
        "prompt": "Implement solve(values) that returns a result.",
        "expected_behavior": "Returns a list of integers.",
        "constraints": "",
        "reference_solution": "def solve(values):\n    return [v for v in values if v > 0]\n",
    }
    defaults.update(overrides)
    return Scenario.from_dict(defaults)


@pytest.fixture
def scenario_factory():
    return make_scenario


@pytest.fixture
def flawed_checkout_path() -> Path:
    return EXAMPLES / "flawed-checkout.yaml"


@pytest.fixture
def clean_scenario_path() -> Path:
    return EXAMPLES / "clean-window-region.yaml"