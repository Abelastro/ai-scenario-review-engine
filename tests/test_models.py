"""Model layer tests: YAML (de)serialization and validation."""

from __future__ import annotations

import pytest

from scenario_review.models import Scenario, Severity


def test_from_dict_roundtrip(scenario_factory):
    scenario = scenario_factory(id="demo", title="Demo", stack="python")
    restored = Scenario.from_dict(scenario.to_dict())
    assert restored == scenario


def test_missing_required_field_raises():
    with pytest.raises(ValueError, match="missing required field"):
        Scenario.from_dict({"id": "x"})


def test_optional_fields_default(scenario_factory):
    scenario = Scenario.from_dict({"id": "x", "title": "T", "prompt": "Do a thing."})
    assert scenario.stack == "unspecified"
    assert scenario.expected_behavior == ""
    assert scenario.constraints == ""
    assert scenario.reference_solution == ""


def test_metadata_is_copied(scenario_factory):
    scenario = scenario_factory(metadata={"source": "internal"})
    assert scenario.metadata["source"] == "internal"
    assert scenario.to_dict()["metadata"] == {"source": "internal"}


def test_severity_weights_ordered():
    assert Severity.CRITICAL.weight > Severity.HIGH.weight > Severity.MEDIUM.weight


def test_from_yaml_missing_file(tmp_path):
    with pytest.raises(OSError):
        Scenario.from_yaml(tmp_path / "nope.yaml")