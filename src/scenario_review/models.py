"""Core data model for the scenario review engine.

A :class:`Scenario` is a machine-readable description of a task an AI assistant may be
asked to solve (a "training scenario"). The engine runs :class:`ReviewRule` checks over
the scenario and produces a :class:`ReviewReport` with typed :class:`Issue` findings and
rubric dimension scores.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

import yaml


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

    @property
    def weight(self) -> float:
        return SEVERITY_WEIGHT[self]


SEVERITY_RANK = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.LOW: 3,
    Severity.INFO: 4,
}

SEVERITY_WEIGHT = {
    Severity.CRITICAL: 1.5,
    Severity.HIGH: 1.0,
    Severity.MEDIUM: 0.6,
    Severity.LOW: 0.3,
    Severity.INFO: 0.1,
}


@dataclass(frozen=True)
class Issue:
    """A single finding produced by a rule."""

    rule_id: str
    category: str
    severity: Severity
    message: str
    evidence: str = ""
    suggestion: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "category": self.category,
            "severity": self.severity.value,
            "message": self.message,
            "evidence": self.evidence,
            "suggestion": self.suggestion,
        }


@dataclass(frozen=True)
class Scenario:
    """A training/evaluation scenario in a machine-readable form."""

    id: str
    title: str
    stack: str
    prompt: str
    expected_behavior: str = ""
    constraints: str = ""
    reference_solution: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Scenario":
        required = {"id", "title", "prompt"}
        missing = required - set(data)
        if missing:
            raise ValueError(f"scenario missing required field(s): {sorted(missing)}")
        return cls(
            id=str(data["id"]),
            title=str(data["title"]),
            stack=str(data.get("stack", "unspecified")),
            prompt=str(data["prompt"]),
            expected_behavior=str(data.get("expected_behavior", "")),
            constraints=str(data.get("constraints", "")),
            reference_solution=str(data.get("reference_solution", "")),
            metadata=dict(data.get("metadata", {}) or {}),
        )

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Scenario":
        raw = Path(path).read_text(encoding="utf-8")
        data = yaml.safe_load(raw) or {}
        if not isinstance(data, dict):
            raise ValueError(f"{path}: YAML root must be a mapping")
        return cls.from_dict(data)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "stack": self.stack,
            "prompt": self.prompt,
            "expected_behavior": self.expected_behavior,
            "constraints": self.constraints,
            "reference_solution": self.reference_solution,
            "metadata": dict(self.metadata),
        }


DIMENSIONS = ("clarity", "correctness", "edge_case_coverage", "safety", "testability")

DIMENSION_LABELS = {
    "clarity": "Clarity",
    "correctness": "Correctness",
    "edge_case_coverage": "Edge-case coverage",
    "safety": "Safety",
    "testability": "Testability",
}

_TITLE_FALLBACK_RE = re.compile(r"[^A-Za-z0-9_]+")


@dataclass
class DimensionScore:
    dimension: str
    score: float
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "label": DIMENSION_LABELS.get(self.dimension, self.dimension),
            "score": round(self.score, 1),
            "rationale": self.rationale,
        }


@dataclass
class ReviewReport:
    scenario: Scenario
    issues: list[Issue] = field(default_factory=list)
    dimension_scores: list[DimensionScore] = field(default_factory=list)
    summary: str = ""
    engine_version: str = ""
    rules_run: int = 0

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    def counts_by_severity(self) -> dict[str, int]:
        counts = {s.value: 0 for s in Severity}
        for issue in self.issues:
            counts[issue.severity.value] += 1
        return counts

    def counts_by_category(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for issue in self.issues:
            counts[issue.category] = counts.get(issue.category, 0) + 1
        return counts

    @property
    def overall_score(self) -> float:
        if not self.dimension_scores:
            return 0.0
        return round(sum(d.score for d in self.dimension_scores) / len(self.dimension_scores), 1)

    def sorted_issues(self) -> list[Issue]:
        return sorted(self.issues, key=lambda i: (SEVERITY_RANK[i.severity], i.rule_id))

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario.to_dict(),
            "engine_version": self.engine_version,
            "rules_run": self.rules_run,
            "score": self.overall_score,
            "dimensions": [d.to_dict() for d in self.dimension_scores],
            "totals": self.counts_by_severity(),
            "issues": [i.to_dict() for i in self.sorted_issues()],
            "summary": self.summary,
        }