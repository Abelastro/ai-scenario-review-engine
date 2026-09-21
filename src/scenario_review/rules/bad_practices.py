"""BP-* rules: bad practices and safety issues in reference solutions."""

from __future__ import annotations

import re

from ..models import Severity
from .base import ReviewContext, ReviewRule
from .logical_flaws import snippet


class EvalExecRule(ReviewRule):
    rule_id = "BP-001"
    name = "EvalExecRule"
    category = "safety"
    default_severity = Severity.HIGH
    description = "Flags eval()/exec()/compile(..., 'exec') code-execution sinks."

    PATTERNS = (
        (re.compile(r"\beval\s*\(", re.I), "eval("),
        (re.compile(r"\bexec\s*\(", re.I), "exec("),
        (re.compile(r'\bcompile\s*\([^,]+,\s*[^,]+,\s*["\']exec["\']', re.I), "compile(..., 'exec')"),
    )

    def check(self, scenario, context: ReviewContext) -> list:
        code = context.code
        if not code.strip():
            return []
        hits = [label for pattern, label in self.PATTERNS if pattern.search(code)]
        if not hits:
            return []
        return [
            self.issue(
                "Code-execution sink in reference solution",
                evidence=", ".join(hits),
                suggestion=(
                    "If input is untrusted this is remote code execution. Replace with a "
                    "safe parser (ast.literal_eval, a real expression evaluator, or a "
                    "whitelist-based dispatch)."
                ),
            )
        ]


SQL_FSTRING = re.compile(
    r"[fr]?['\"](?=[^'\"\n]*(select|insert|update|delete|drop|alter|create table|truncate))[^'\"\n]*\{[^}\"']*\}[^'\"\n]*['\"]",
    re.I,
)
SQL_FORMAT = re.compile(
    r"['\"](?=[^'\"\n]*(select|insert|update|delete|drop))[^'\"\n]*\{[^}\"']*\}[^'\"\n]*['\"]\s*\.\s*format\s*\(",
    re.I,
)
SQL_PERCENT = re.compile(
    r"['\"](?=[^'\"\n]*(select|insert|update|delete|drop|where))[^'\"\n]*%s[^'\"\n]*['\"]\s*%",
    re.I,
)


class SqlInterpolationRule(ReviewRule):
    rule_id = "BP-002"
    name = "SqlInterpolationRule"
    category = "safety"
    default_severity = Severity.HIGH
    description = "Flags SQL built via string interpolation (injection risk)."

    def check(self, scenario, context: ReviewContext) -> list:
        code = context.code
        if not code.strip():
            return []
        hits = []
        for label, pattern in (
            ("f-string SQL", SQL_FSTRING),
            (".format() SQL", SQL_FORMAT),
            ("%s-style SQL", SQL_PERCENT),
        ):
            if pattern.search(code):
                hits.append(label)
        if not hits:
            return []
        return [
            self.issue(
                "SQL built with string interpolation",
                evidence=", ".join(hits),
                suggestion=(
                    "Parameterize: psycopg2/asyncpg placeholders (%s / $1) or ORM rows. "
                    "Never interpolate identifiers or ORDER BY clauses without a whitelist."
                ),
            )
        ]


SECRET_ASSIGN = re.compile(
    r"\b(password|passwd|api[_-]?key|secret|access[_-]?token|auth[_-]?token|private[_-]?key|pk[_-]?[a-z])"
    r"\s*[=:]\s*['\"][^'\"]{6,}['\"]",
    re.I,
)


class HardcodedSecretRule(ReviewRule):
    rule_id = "BP-003"
    name = "HardcodedSecretRule"
    category = "safety"
    default_severity = Severity.HIGH
    description = "Flags hardcoded credentials in spec or reference solution."

    def check(self, scenario, context: ReviewContext) -> list:
        text = context.all_text()
        if not text.strip():
            return []
        m = SECRET_ASSIGN.search(text)
        if not m:
            return []
        return [
            self.issue(
                "Hardcoded secret-like value found",
                evidence=snippet(text, m.span(), 30),
                suggestion=(
                    "Pull credentials from the environment or a secret store and never "
                    "write literals into code or training data."
                ),
            )
        ]


class BroadExceptRule(ReviewRule):
    rule_id = "BP-004"
    name = "BroadExceptRule"
    category = "correctness"
    default_severity = Severity.MEDIUM
    description = "Flags bare/broad except clauses that hide the failure mode."

    PATTERNS = (
        (re.compile(r"^\s*except\s*:\s*$", re.M), "bare 'except:'"),
        (re.compile(r"^\s*except Exception\s*:\s*$", re.M), "'except Exception:'"),
        (re.compile(r"^\s*except Exception as [\w_]+:\s*$", re.M), "'except Exception as e:'"),
    )

    def check(self, scenario, context: ReviewContext) -> list:
        code = context.code
        if not code.strip():
            return []
        hits = []
        for pattern, label in self.PATTERNS:
            for m in pattern.finditer(code):
                hits.append(f"{label} (line {code.count(chr(10), 0, m.start()) + 1})")
                break
        if not hits:
            return []
        return [
            self.issue(
                "Overly broad exception handling",
                evidence="; ".join(hits[:3]),
                suggestion=(
                    "Catch specific exceptions and let unknown ones propagate; log the "
                    "context (exception type, message, traceback) at every catch site."
                ),
            )
        ]


SWALLOWED = re.compile(
    r"except[^\n]*:\s*\n(\s*)(pass|continue)\b",
    re.I,
)


class SwallowedExceptionRule(ReviewRule):
    rule_id = "BP-005"
    name = "SwallowedExceptionRule"
    category = "correctness"
    default_severity = Severity.HIGH
    description = "Flags exception handlers that silently pass/continue."

    def check(self, scenario, context: ReviewContext) -> list:
        code = context.code
        if not code.strip():
            return []
        hits = list(SWALLOWED.finditer(code))
        if not hits:
            return []
        lines = []
        for m in hits[:3]:
            line = code.count(chr(10), 0, m.start()) + 1
            payload = m.group(2)
            lines.append(f"line {line}: silently '{payload}'")
        return [
            self.issue(
                "Exception swallowed without surfacing",
                evidence="; ".join(lines),
                suggestion=(
                    "Log with context and decide the failure policy: retry, dead-letter, "
                    "or fail fast. Silent 'pass' hides bugs from every downstream consumer."
                ),
            )
        ]


MUTABLE_DEFAULT = re.compile(
    r"\bdef\s+\w+\s*\([^)]*(=\s*\[[^\]]*\]|=?\s*\{\s*\}|=?\s*set\s*\(\))",
    re.I,
)


class MutableDefaultArgsRule(ReviewRule):
    rule_id = "BP-006"
    name = "MutableDefaultArgsRule"
    category = "correctness"
    default_severity = Severity.MEDIUM
    description = "Flags mutable default arguments (shared-state bug)."

    def check(self, scenario, context: ReviewContext) -> list:
        code = context.code
        if not code.strip():
            return []
        m = MUTABLE_DEFAULT.search(code)
        if not m:
            return []
        return [
            self.issue(
                "Mutable default argument",
                evidence=m.group(0)[:70],
                suggestion="Use None as the default and construct the mutable inside the function body.",
            )
        ]


class PrintAsLoggingRule(ReviewRule):
    rule_id = "BP-007"
    name = "PrintAsLoggingRule"
    category = "testability"
    default_severity = Severity.LOW
    description = "Suggests structured logging over print() in library code."

    def check(self, scenario, context: ReviewContext) -> list:
        code = context.code
        if not code.strip() or "def " not in code:
            return []
        if re.search(r"\bprint\s*\(", code) and not re.search(r"\blogging\b|logger\.", code, re.I):
            return [
                self.issue(
                    "print() used where structured logging fits",
                    evidence="print( in function definitions",
                    suggestion=(
                        "Use logging with levels + structured fields (logger.info('charged', extra={...})) "
                        "so operators and tests can observe behavior without parsing stdout."
                    ),
                )
            ]
        return []


class ShellTrueRule(ReviewRule):
    rule_id = "BP-008"
    name = "ShellTrueRule"
    category = "safety"
    default_severity = Severity.MEDIUM
    description = "Flags shell=True / os.system() / string-command subprocess calls."

    PATTERNS = (
        (re.compile(r"\bshell\s*=\s*True\b", re.I), "subprocess shell=True"),
        (re.compile(r"\bos\.system\s*\(", re.I), "os.system("),
        (re.compile(r"\bsubprocess\.(Popen|run|call|check_output)\([^)]*\bshell\s*=\s*True", re.I), "subprocess with shell=True"),
    )

    def check(self, scenario, context: ReviewContext) -> list:
        code = context.code
        if not code.strip():
            return []
        hits = [label for pattern, label in self.PATTERNS if pattern.search(code)]
        if not hits:
            return []
        return [
            self.issue(
                "Shell execution with a string command",
                evidence=", ".join(hits),
                suggestion=(
                    "Pass argument lists without shell=True; if a shell string is truly "
                    "required, validate/quote every interpolated value."
                ),
            )
        ]


class UnsafePickleRule(ReviewRule):
    rule_id = "BP-009"
    name = "UnsafePickleRule"
    category = "safety"
    default_severity = Severity.MEDIUM
    description = "Flags pickle on potentially untrusted data."

    def check(self, scenario, context: ReviewContext) -> list:
        code = context.code
        if not code.strip():
            return []
        m = re.search(r"\b(pickle|joblib|dill)\.(loads?|dump)\(?", code)
        if not m:
            return []
        return [
            self.issue(
                "pickle/joblib/dill used (arbitrary code execution on load)",
                evidence=m.group(0),
                suggestion=(
                    "Only unpickle data you produced yourself in a trusted pipeline. "
                    "For untrusted input use a safe formats: JSON + schema, parquet, or "
                    "msgpack."
                ),
            )
        ]