"""EC-* rules: edge cases overlooked by scenario specs and reference solutions."""

from __future__ import annotations

import re

from ..models import Severity
from .base import ReviewContext, ReviewRule


class FloatEqualityRule(ReviewRule):
    rule_id = "EC-001"
    name = "FloatEqualityRule"
    category = "correctness"
    default_severity = Severity.MEDIUM
    description = "Flags float equality comparisons and float currency math."

    PATTERNS = (
        (re.compile(r"==\s*-?\d+\.\d+|!=\s*-?\d+\.\d+", re.I), "float equality comparison"),
        (re.compile(r"\*\s*0\.1+\b|/\s*0\.*(1|2|3|5|7)\b(?!\d)", re.I), "float multiplier on money"),
        (re.compile(r"\bround\([^,)]*,\s*2\)", re.I), "round(x, 2) float rounding"),
    )

    def check(self, scenario, context: ReviewContext) -> list:
        code = context.code
        if not code.strip():
            return []
        hits = []
        for pattern, label in self.PATTERNS:
            for m in pattern.finditer(code):
                hits.append(f"{label} ({m.group(0)[:40]})")
                break
        if not hits:
            return []
        return [
            self.issue(
                "Floating-point comparison or currency math",
                evidence="; ".join(hits[:3]),
                suggestion=(
                    "Money should be cents as int, or Decimal with explicit rounding "
                    "(ROUND_HALF_EVEN); compare with math.isclose and an explicit rel/abs "
                    "tolerance. Never rely on == 0.1-style checks."
                ),
            )
        ]


class NullHandlingRule(ReviewRule):
    rule_id = "EC-002"
    name = "NullHandlingRule"
    category = "edge_case_coverage"
    default_severity = Severity.MEDIUM
    description = "Flags code that reads into structures without defining None/missing behavior."

    ACCESS = re.compile(r"\[['\"]|\[0\]|\.get\(['\"]|\.\.\.|\bmembers?\b|\brows?\b", re.I)
    GUARDED = re.compile(r"\bis None\b|\bnot None\b|\.get\(|try:|except (KeyError|IndexError|TypeError)|or \{\}|or \[\]|defaultdict", re.I)

    def check(self, scenario, context: ReviewContext) -> list:
        code, spec = context.code, context.spec
        if not code.strip():
            return []
        if not self.ACCESS.search(code) or self.GUARDED.search(code + "\n" + spec):
            return []
        if not re.search(r"\b(optional|nullable|may be (None|missing)|missing|absent)\b", spec, re.I):
            return [
                self.issue(
                    "None/missing-value behavior undefined",
                    evidence="spec never mentions None or missing keys; reference reads structures directly",
                    suggestion=(
                        "State it: 'fields may be missing; treat as zero/None' plus a golden "
                        "example with a partial record. Guard with explicit checks or a schema."
                    ),
                )
            ]
        return []


class ConcurrencyLockRule(ReviewRule):
    rule_id = "EC-003"
    name = "ConcurrencyLockRule"
    category = "edge_case_coverage"
    default_severity = Severity.MEDIUM
    description = "Flags shared mutable state mutated from parallel workers without synchronization."

    CONCURRENCY = (
        re.compile(r"\bthreading\.(Thread|Lock|RLock)|ThreadPoolExecutor|ProcessPoolExecutor|asyncio\.(gather|create_task)\b", re.I),
        re.compile(r"\bmultiprocessing\.|concurrent\.futures", re.I),
    )
    MUTATION = re.compile(r"\[['\"\w]+\]\s*[+\-]?=|\.append\(|\.add\(|\.update\(|\+=|count\s*[+\-]=", re.I)
    SYNC = re.compile(r"Lock|Semaphore|Queue|Event|Condition|Barrier|threading\.|asyncio\.Lock|pool\.map", re.I)

    def check(self, scenario, context: ReviewContext) -> list:
        code = context.code
        if not code.strip():
            return []
        concurrent = any(p.search(code) for p in self.CONCURRENCY)
        mutated = bool(self.MUTATION.search(code))
        if not (concurrent and mutated) or self.SYNC.search(code):
            return []
        return [
            self.issue(
                "Shared state mutated under concurrency without synchronization",
                evidence="concurrency primitive present alongside dict/list/counter mutation",
                suggestion=(
                    "Use a lock around each mutation (or a thread-safe structure: queue.Queue, "
                    "atomic counters). For asyncio, prefer asyncio.Lock or process via tasks "
                    "that return values instead of mutating shared dicts."
                ),
            )
        ]


class UnboundedRetriesRule(ReviewRule):
    rule_id = "EC-004"
    name = "UnboundedRetriesRule"
    category = "edge_case_coverage"
    default_severity = Severity.MEDIUM
    description = "Flags retry loops without a cap or backoff."

    LOOP_OP = re.compile(
        r"\bwhile\s+[Tt]rue\b|\bwhile\s+not (done|ok|success|ready)\b|for attempt in range\(",
        re.I,
    )
    NETWORK = re.compile(r"requests\.(get|post|put|delete|patch)|urlopen|aiohttp|urllib|\.retry\(|retrying\(|tenacity", re.I)
    BACKOFF_HINT = re.compile(r"max[_ \w]*\d|attempt(?:_\w*)?\s*[<>=]|backoff|back_off|jitter|sleep\(|timeout|cap|limit", re.I)

    def check(self, scenario, context: ReviewContext) -> list:
        code = context.code
        if not code.strip():
            return []
        if not self.LOOP_OP.search(code) or not self.NETWORK.search(code):
            return []
        if self.BACKOFF_HINT.search(code):
            return []
        return [
            self.issue(
                "Retry loop with no cap or backoff",
                evidence="while-loop around a network call with no max-attempts guard",
                suggestion=(
                    "Cap attempts (e.g. 3-5), sleep with exponential backoff + jitter "
                    "(base * 2**attempt + random), and honor Retry-After when present."
                ),
            )
        ]


class IdempotencyRetryRule(ReviewRule):
    rule_id = "EC-005"
    name = "IdempotencyRetryRule"
    category = "edge_case_coverage"
    default_severity = Severity.MEDIUM
    description = "Flags event/webhook/cron scenarios that never discuss duplicate delivery."

    IDEMPOTENCY_TRIGGER = re.compile(r"\b(webhook|callback|retry|reprocess|scheduler|cron|queue|message|batch job|consumer|event)\b", re.I)
    IDEMPOTENCY_MENTION = re.compile(r"\b(idempoten|dedup|upsert|on conflict|checkpoint|cursor|unique key|at[- ]least[- ]once|guaranteed[- ]delivery|replay|duplicate|double[- ]?count(ed)?|exact(ly)?[- ]once|processed|seen)\b", re.I)

    def check(self, scenario, context: ReviewContext) -> list:
        text = context.all_text()
        if not text.strip():
            return []
        if not self.IDEMPOTENCY_TRIGGER.search(text):
            return []
        if self.IDEMPOTENCY_MENTION.search(text):
            return []
        return [
            self.issue(
                "Duplicate delivery semantics never discussed",
                evidence="spec mentions webhook/queue/cron-style processing without idempotency",
                suggestion=(
                    "Define how duplicates are handled: idempotency key in the payload, "
                    "UNIQUE constraint, or a processed-keys store; state exactly what "
                    "happens when the same event arrives twice."
                ),
            )
        ]


class LargeInputRule(ReviewRule):
    rule_id = "EC-006"
    name = "LargeInputRule"
    category = "edge_case_coverage"
    default_severity = Severity.LOW
    description = "Flags whole-file loads when scale is unbounded."

    WHOLE_FILE = re.compile(r"\.(read|readlines|read_text)\s*\(\)|open\([^)]*\)\.read\(\)|json\.load\(|pd\.read_csv\(|pd\.read_sql\(", re.I)
    MENTION_SCALE = re.compile(r"\b(chunk|stream|batch|limit|window|page|partition|10[0-9]{2,}|million|billion)\b", re.I)

    def check(self, scenario, context: ReviewContext) -> list:
        code, spec = context.code, context.spec
        if not code.strip():
            return []
        if not self.WHOLE_FILE.search(code):
            return []
        if self.MENTION_SCALE.search(code) or self.MENTION_SCALE.search(spec):
            return []
        return [
            self.issue(
                "Whole-file load with no scale discussion",
                evidence="reads entire file into memory",
                suggestion=(
                    "Specify the input envelope (rows, size class) and prefer "
                    "streaming/chunked reads, or make the resource bound explicit."
                ),
            )
        ]


class UnicodeEncodingRule(ReviewRule):
    rule_id = "EC-007"
    name = "UnicodeEncodingRule"
    category = "edge_case_coverage"
    default_severity = Severity.LOW
    description = "Flags implicit or lossy text encoding assumptions."

    OPEN_CALL = re.compile(r"open\s*\([^)]{0,200}\)", re.I)

    def check(self, scenario, context: ReviewContext) -> list:
        code = context.code
        if not code.strip():
            return []
        findings = []
        for call in self.OPEN_CALL.finditer(code):
            call_text = call.group(0)
            if "encoding" in call_text:
                continue
            findings.append(
                self.issue(
                    "open() without explicit encoding= (Python 3)",
                    evidence=call_text[:60],
                    suggestion=(
                        "Pass encoding='utf-8' explicitly; on many platforms the default "
                        "locale encoding varies, so the same scenario can behave "
                        "differently across machines."
                    ),
                    severity=Severity.LOW,
                )
            )
            break
        if re.search(r"\.encode\s*\(\s*['\"]ascii['\"]", code):
            findings.append(
                self.issue(
                    "encode('ascii') can raise on non-ASCII data",
                    evidence="encode('ascii') in reference",
                    suggestion="Use encode('utf-8') or handle UnicodeEncodeError explicitly.",
                    severity=Severity.MEDIUM,
                )
            )
        if re.search(r"['\"]latin[- ]?1['\"]", code, re.I):
            findings.append(
                self.issue(
                    "latin-1 assumed encoding",
                    evidence="latin-1 literal found",
                    suggestion="Confirm the data contract; prefer utf-8 for interchange.",
                    severity=Severity.LOW,
                )
            )
        return findings


class ExternalCallTimeoutRule(ReviewRule):
    rule_id = "EC-008"
    name = "ExternalCallTimeoutRule"
    category = "edge_case_coverage"
    default_severity = Severity.HIGH
    description = "Flags external HTTP calls without a timeout (hang risk)."

    HTTP_CALL = re.compile(r"\b(requests\.(get|post|put|delete|patch|head)|urlopen\s*\(|aiohttp\.|httpx\.(get|post|put|delete|patch))\b", re.I)
    HAS_TIMEOUT = re.compile(r"timeout\s*=|timeout:", re.I)

    def check(self, scenario, context: ReviewContext) -> list:
        code = context.code
        if not code.strip():
            return []
        if not self.HTTP_CALL.search(code):
            return []
        if self.HAS_TIMEOUT.search(code):
            return []
        return [
            self.issue(
                "External call without timeout",
                evidence="HTTP call with no timeout= argument",
                suggestion=(
                    "Always set an explicit timeout (connect + read), e.g. "
                    "requests.get(url, timeout=(3.05, 10)). Then define behavior: retry "
                    "with backoff, degrade, or fail fast."
                ),
            )
        ]


class DataShapeValidationRule(ReviewRule):
    rule_id = "EC-009"
    name = "DataShapeValidationRule"
    category = "testability"
    default_severity = Severity.LOW
    description = "Suggests explicit shape validation when parsing untrusted structured data."

    JSON_PARSE = re.compile(r"\bjson\.(loads?|load)\s*\(", re.I)
    SCHEMA_HINT = re.compile(r"\b(schema|pydantic|jsonschema|dataclass|typeddict|marshmallow|validate|attrs|dataclasses)\b", re.I)

    def check(self, scenario, context: ReviewContext) -> list:
        code, spec = context.code, context.spec
        if not code.strip():
            return []
        if not self.JSON_PARSE.search(code):
            return []
        if self.SCHEMA_HINT.search(code + "\n" + spec):
            return []
        return [
            self.issue(
                "Parsed JSON without explicit shape validation",
                evidence="json.loads(...) with no schema/dataclass validation in sight",
                suggestion=(
                    "Validate at the boundary with a schema (jsonschema/pydantic) so "
                    "missing fields, wrong types, and extra keys are handled explicitly "
                    "instead of raising KeyError deep in business logic."
                ),
            )
        ]