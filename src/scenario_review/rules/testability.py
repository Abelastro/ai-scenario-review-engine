"""TB-* rules: testability gaps — can candidate answers actually be verified?"""

from __future__ import annotations

import re

from ..models import Severity
from .base import ReviewContext, ReviewRule

class MissingExampleInputsRule(ReviewRule):
    rule_id = "TB-001"
    name = "MissingExampleInputsRule"
    category = "testability"
    default_severity = Severity.MEDIUM
    description = "Flags specs with no concrete example input/output pair."

    EXAMPLES_HINT = re.compile(r"\b(example|sample|for instance|e\.g\.|input[:=]|output[:=][\s\S]{0,80}|\{[\"']|\bInput:|`[^`]{5,}`)", re.I)

    def check(self, scenario, context: ReviewContext) -> list:
        spec = context.spec
        if not spec.strip():
            return []
        if self.EXAMPLES_HINT.search(spec):
            return []
        return [
            self.issue(
                "No concrete example input/output pair",
                evidence="spec is prose-only; no sample values or code blocks",
                suggestion=(
                    "Add 2-3 golden pairs. They double as unit tests, calibrate the "
                    "assistant's output format, and make grader criteria objective. "
                    "Include a happy path and at least one boundary case."
                ),
            )
        ]


class GoldenExpectationRule(ReviewRule):
    rule_id = "TB-002"
    name = "GoldenExpectationRule"
    category = "testability"
    default_severity = Severity.MEDIUM
    description = "Flags scenarios that never state the expected observable output."

    GOLDEN_HINT = re.compile(r"\b(expected|expect |golden|assert|verify|must return|returns? (\d|[\[\"'({])|output:|=>|should be\b)", re.I)

    def check(self, scenario, context: ReviewContext) -> list:
        text = context.all_text()
        if not text.strip():
            return []
        if self.GOLDEN_HINT.search(text):
            return []
        return [
            self.issue(
                "No golden expectation stated",
                evidence="in the spec, an observable output is never pinned to a value",
                suggestion=(
                    "State exact expected outputs ('returns 2450.00 as a string with two "
                    "decimals') or at minimum a verifiable property ('result is the "
                    "monotonically increasing subset of the input')."
                ),
            )
        ]


HEDGE_VERBS = (
    (r"\bshould (typically|generally|probably)\b", "'should typically/probably'"),
    (r"\bideally\b", "'ideally'"),
    (r"\bpreferably\b", "'preferably'"),
    (r"\bwhen (deemed|considered) appropriate\b", "'when appropriate'"),
    (r"\bas needed\b", "'as needed'"),
    (r"\bmay also\b", "'may also'"),
)


class VagueAcceptanceVerbsRule(ReviewRule):
    rule_id = "TB-003"
    name = "VagueAcceptanceVerbsRule"
    category = "testability"
    default_severity = Severity.LOW
    description = "Flags hedge verbs in the expected-behavior text (unverifiable)."

    def check(self, scenario, context: ReviewContext) -> list:
        behavior = context.scenario.expected_behavior
        if not behavior.strip():
            return []
        hits = [label for pattern, label in HEDGE_VERBS if re.search(pattern, behavior, re.I)]
        if not hits:
            return []
        return [
            self.issue(
                "Hedged acceptance criteria in expected behavior",
                evidence=", ".join(hits),
                suggestion=(
                    "Rewrite with normative verbs ('must', 'returns', 'raises') and "
                    "explicit conditions so a grader can decide pass/fail mechanically."
                ),
            )
        ]


ENV_TIES = (
    (re.compile(r"\blocalhost(:\d+)?\b|\b127\.0\.0\.1\b", re.I), "localhost/127.0.0.1 pinning"),
    (re.compile(r"\b/var/\w+|\b/etc/\w+|C:\\\\", re.I), "absolute filesystem paths"),
    (re.compile(r"\b(fixed|hardcoded) (path|url|port)\b", re.I), "'fixed path/url/port'"),
)

class HiddenEnvironmentDepsRule(ReviewRule):
    rule_id = "TB-004"
    name = "HiddenEnvironmentDepsRule"
    category = "testability"
    default_severity = Severity.MEDIUM
    description = "Flags scenarios that hardwire environment dependencies."

    ABSTRACTION_HINT = re.compile(r"\b(config|env|inject|mock|credential|settings|service locator|dependency)", re.I)

    def check(self, scenario, context: ReviewContext) -> list:
        text = context.all_text()
        if not text.strip():
            return []
        hits = [label for pattern, label in ENV_TIES if pattern.search(text)]
        if not hits or self.ABSTRACTION_HINT.search(text):
            return []
        return [
            self.issue(
                "Environment dependencies hardwired",
                evidence=", ".join(hits),
                suggestion=(
                    "Parameterize via config/env and inject dependencies (HTTP clients, "
                    "DB handles) so the scenario is reproducible on any machine and "
                    "gradeable in a sandbox."
                ),
            )
        ]