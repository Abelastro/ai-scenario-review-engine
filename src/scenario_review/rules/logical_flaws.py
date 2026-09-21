"""LF-* rules: logical flaws in the scenario specification.

These checks target the *spec text* (prompt, expected behavior, constraints) and the
reference solution for contradictions, vague criteria, and boundary traps. They are
heuristics — every finding is phrased as something to verify, with the evidence that
triggered it.
"""

from __future__ import annotations

import re

from ..models import Severity
from .base import ReviewContext, ReviewRule


def snippet(text: str, span: tuple[int, int], radius: int = 40) -> str:
    """Extract a compact single-line snippet around a match span."""
    start = max(0, span[0] - radius)
    end = min(len(text), span[1] + radius)
    return text[start:end].replace("\n", " ").strip()

VAGUE_TOKENS: "tuple[tuple[str, str], ...]" = (
    (r"\betc\.?", "trailing 'etc.'"),
    (r"\band so on\b", "'and so on'"),
    (r"\bhandle errors properly\b", "'handle errors properly'"),
    (r"\bhandle (edge cases|boundaries) appropriately", "'handle ... appropriately'"),
    (r"\bgood practices?\b", "'good practice'"),
    (r"\bbest practices?\b", "'best practice'"),
    (r"\brobust(ly)?\b", "'robust'"),
    (r"\befficient(ly)?\b", "'efficient'"),
    (r"\bwell[- ]?structured\b", "'well-structured'"),
    (r"\bappropriate(ly)?\b", "'appropriate'"),
    (r"\bproper(ly)?\b", "'proper'"),
    (r"\bas needed\b|\bas necessary\b", "'as needed/necessary'"),
    (r"\breasonable(ly)?\b", "'reasonable'"),
    (r"\bsufficient(ly)?\b", "'sufficient'"),
)


class UndefinedTermsRule(ReviewRule):
    rule_id = "LF-001"
    name = "UndefinedTermsRule"
    category = "clarity"
    default_severity = Severity.LOW
    description = "Flags vague, unmeasurable terms in the scenario spec."

    def check(self, scenario, context: ReviewContext) -> list:
        spec = context.spec
        if not spec.strip():
            return []
        hits = [(pattern, label) for pattern, label in VAGUE_TOKENS if re.search(pattern, spec, re.I)]
        if not hits:
            return []
        evidence = ", ".join(label for _, label in hits[:6])
        return [
            self.issue(
                "Spec relies on undefined evaluation terms",
                evidence=evidence,
                suggestion=(
                    "Replace each vague term with a concrete, testable criterion. "
                    "'handle errors properly' -> 'recover from a failed payment by retrying "
                    "with exponential backoff, max 3 attempts, then raising PaymentFailed'."
                ),
            )
        ]


CONTRADICTION_PAIRS: tuple[tuple[re.Pattern, re.Pattern, str], ...] = (
    (
        re.compile(r"\bnever return\s+(None|null|nil)\b", re.I),
        re.compile(r"\breturn\s+(None|null|nil)\b\s+(when|if|unless)", re.I),
        "null-return policy",
    ),
    (
        re.compile(r"\bmust not raise\b", re.I),
        re.compile(r"\braise (an? )?(exception|error)\b", re.I),
        "exception policy",
    ),
    (
        re.compile(r"\bnever (fail|crash)\b", re.I),
        re.compile(r"\bfail(ure|s)?\b|except", re.I),
        "failure handling",
    ),
    (
        re.compile(r"\b(process|handle) (all|every) (item|record|row|request)\b", re.I),
        re.compile(r"\bskip (invalid|bad|malformed|failed)\b", re.I),
        "all-vs-skip policy",
    ),
    (
        re.compile(r"\bmust be idempotent\b|\bretry[-\w ]*safe\b", re.I),
        re.compile(r"\binsert\b(?!.*(on conflict|upsert|unique))", re.I),
        "idempotency vs plain insert",
    ),
)


class ContradictoryRequirementsRule(ReviewRule):
    rule_id = "LF-002"
    name = "ContradictoryRequirementsRule"
    category = "correctness"
    default_severity = Severity.MEDIUM
    description = "Flags spec clauses that may directly contradict each other."

    def check(self, scenario, context: ReviewContext) -> list:
        spec = context.spec
        if not spec.strip():
            return []
        findings = []
        for left, right, label in CONTRADICTION_PAIRS:
            lm, rm = left.search(spec), right.search(spec)
            if lm and rm:
                findings.append(
                    self.issue(
                        f"Possibly contradictory requirements about {label}",
                        evidence=(
                            f"'{lm.group(0)[:60]}...' appears alongside "
                            f"'{rm.group(0)[:60]}...'"
                        ),
                        suggestion=(
                            "State the precedence explicitly (e.g. 'on partial failure, "
                            "record and continue; on invalid input, raise')."
                        ),
                    )
                )
        return findings


NON_MEASURABLE: tuple[tuple[str, str], ...] = (
    (r"\bfast(er|est)?\b", "'fast'"),
    (r"\bquick(ly)?\b", "'quickly'"),
    (r"\bslow(ly)?\b", "'slow'"),
    (r"\bminimal\b", "'minimal'"),
    (r"\bsmall(est)?\b", "'small'"),
    (r"\blarge(st)?\b", "'large'"),
    (r"\bscalable\b", "'scalable'"),
    (r"\bhigh[- ]?performance\b", "'high-performance'"),
    (r"\boptimized?\b", "'optimized'"),
    (r"\bclean code\b", "'clean code'"),
    (r"\breadable\b", "'readable'"),
)

MEASURE_RE = re.compile(
    r"\d+(\.\d+)?\s*(ms|s|sec|seconds?|minutes?|hours?|%|percent|bytes?|kb|mb|gb|"
    r"requests?|rows?|concurrent|items?|records?|gbps|mbps)",
    re.I,
)


class UnverifiableCriteriaRule(ReviewRule):
    rule_id = "LF-003"
    name = "UnverifiableCriteriaRule"
    category = "correctness"
    default_severity = Severity.LOW
    description = "Flags quality adjectives that no test could ever measure."

    def check(self, scenario, context: ReviewContext) -> list:
        spec = context.spec
        if not spec.strip():
            return []
        hits = [label for pattern, label in NON_MEASURABLE if re.search(pattern, spec, re.I)]
        if not hits or MEASURE_RE.search(spec):
            return []
        return [
            self.issue(
                "Acceptance criteria are not measurable",
                evidence=", ".join(hits[:5]),
                suggestion=(
                    "Attach a measure: 'fast' -> 'p95 latency under 200ms on 10k rows'; "
                    "'scalable' -> 'throughput of 1k req/s on a single node'."
                ),
            )
        ]


class OffByOneBoundaryRule(ReviewRule):
    rule_id = "LF-004"
    name = "OffByOneBoundaryRule"
    category = "edge_case_coverage"
    default_severity = Severity.LOW
    description = "Flags loop boundary patterns that skip or overrun a sequence."

    SUSPICIOUS = (
        (re.compile(r"\bfor [\w_]+ in range\((1|2), *len\(", re.I), "loop starts at index 1 (skips first element)"),
        (re.compile(r"\bfor [\w_]+ in range\(len\([\w_.]+\) *\+ *1\)", re.I), "loop range exceeds the collection length"),
        (re.compile(r"\bwhile +\w+ *<= *len\(", re.I), "loop bound '<= len(...)' may walk past the last index"),
        (re.compile(r"\[[-\w_.]+ *- *1\] *== *(" + r"|".join(rf"'{c}'" for c in "abcdefghijklmnopqrstuvwxyz") + r")", re.I), "last-element test that breaks on empty input"),
    )

    def check(self, scenario, context: ReviewContext) -> list:
        code = context.code
        if not code.strip():
            return []
        findings = []
        for pattern, why in self.SUSPICIOUS:
            m = pattern.search(code)
            if m:
                findings.append(
                    self.issue(
                        f"Off-by-one risk: {why}",
                        evidence=self._snippet(code, m.span(), 40),
                        suggestion="Verify the boundary with an explicit test at size 0, 1, and n.",
                    )
                )
        return findings

    @staticmethod
    def _snippet(code: str, span: tuple[int, int], radius: int) -> str:
        start = max(0, span[0] - radius)
        end = min(len(code), span[1] + radius)
        return code[start:end].replace("\n", " ").strip()


COLLECTION_OPS = re.compile(
    r"\bfor [\w_]+ in |\.append\(|\.pop\(|\.extend\(|len\(|sum\(|\.map\(|\.filter\(|\bmap\(|\bfilter\(",
    re.I,
)
EMPTY_COVERED = re.compile(
    r"\b(empty|zero items|no items|nothing to (do|process)|0 (items|rows|records)|\bempty list\b)\b",
    re.I,
)
None_COVERED = re.compile(r"\bif not [\w_.]+(:|\b)|== *\[\]|is None|== None\b", re.I)


class EmptyInputSemanticsRule(ReviewRule):
    rule_id = "LF-005"
    name = "EmptyInputSemanticsRule"
    category = "edge_case_coverage"
    default_severity = Severity.MEDIUM
    description = "Flags scenarios that process collections without defining empty-input behavior."

    def check(self, scenario, context: ReviewContext) -> list:
        code, spec = context.code, context.spec
        if not code.strip() or not COLLECTION_OPS.search(code):
            return []
        if EMPTY_COVERED.search(spec) or EMPTY_COVERED.search(code) or None_COVERED.search(code):
            return []
        return [
            self.issue(
                "Empty-input behavior is undefined",
                evidence="reference iterates a collection; neither spec nor solution mentions empty input",
                suggestion=(
                    "State it in the spec: 'Returns 0 for an empty list and does not raise'. "
                    "A golden pair (input: [], output: 0) makes it verifiable."
                ),
            )
        ]


class TimezoneNaiveDateTimeRule(ReviewRule):
    rule_id = "LF-006"
    name = "TimezoneNaiveDateTimeRule"
    category = "edge_case_coverage"
    default_severity = Severity.MEDIUM
    description = "Flags timezone-naive datetime usage in reference solutions."

    NAIVE = (
        (re.compile(r"\bdatetime\.now\(\)|\bdatetime\.utcnow\(\)", re.I), "naive datetime.now()/utcnow()"),
        (re.compile(r"\bdate\.today\(\)", re.I), "naive date.today()"),
    )
    AWARE_MENTION = re.compile(r"timezone|tzinfo|ZoneInfo|UTC|utc|offset", re.I)

    def check(self, scenario, context: ReviewContext) -> list:
        code = context.code
        if not code.strip():
            return []
        hits = [label for pattern, label in self.NAIVE if pattern.search(code)]
        if not hits or self.AWARE_MENTION.search(context.all_text()):
            return []
        return [
            self.issue(
                "Timezone-naive datetime used",
                evidence=", ".join(hits),
                suggestion=(
                    "Use timezone-aware values: datetime.now(timezone.utc) or ZoneInfo. "
                    "Note datetime.utcnow() is deprecated since Python 3.12. "
                    "Decide and document whether the spec expects wall-clock or UTC."
                ),
            )
        ]