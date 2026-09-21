# AI Scenario Review Engine

A systematic, rule-based review engine for **AI training & evaluation scenarios** — the
kind of technical task descriptions used to train and benchmark AI assistants.

The engine reads a scenario (the prompt, expected behavior, constraints, and a reference
solution) and produces a structured review report that flags:

- **Logical flaws** — contradictions, unverifiable criteria, off-by-one traps, undefined terms
- **Edge cases** — nulls, empty input, float precision, concurrency, retries, idempotency, timezones
- **Bad practices** — `eval`/`exec`, SQL string interpolation, hardcoded secrets, swallowed exceptions
- **Safety issues** — code-execution sinks, shell injection, unsafe deserialization, missing timeouts
- **Testability gaps** — missing example inputs, missing golden expectations, vague acceptance verbs

...exactly the review pass a senior engineer would run before a scenario is allowed to
train or evaluate an AI assistant.

## Why this exists

Weak scenarios train weak assistants. A scenario that says *"handle errors properly"*,
compares money with `== 0.1`, or never mentions what to do with an empty input produces
candidate answers that cannot be compared, scored, or trusted. This engine turns that
review from "vibes" into a repeatable, auditable checklist with a rubric score.

## What it looks like

```console
$ scenario-review review examples/scenarios/flawed-checkout.yaml

scenario: Store checkout with discount codes
stack: python

[crit] BP-003 HardcodedSecretRule       discount API key hardcoded in reference solution
[high] BP-002 SqlInterpolationRule      reference solution builds SQL with f-strings
[high] EC-008 ExternalCallTimeoutRule   requests.get(...) without timeout
[high] LF-002 ContradictoryRequirements "must never return null" vs "return None on invalid coupon"
[med ] EC-001 FloatEqualityRule         money compared with float equality
[med ] LF-005 EmptyInputSemanticsRule   empty-cart behavior undefined
[med ] LF-006 TimezoneNaiveDateTimeRule datetime.now() without timezone
[low ] TB-001 MissingExampleInputsRule  no concrete example input/output pair

Score: 2.4 / 5  →  Needs rework (7 findings)
```

## Install

```bash
pip install -e ".[dev]"     # from the repo root
# or
pip install ai-scenario-review-engine
```

## Quickstart

```bash
# review a scenario file
scenario-review review scenario.yaml

# JSON or Markdown report (great for CI or PR comments)
scenario-review review scenario.yaml -f json -o report.json
scenario-review review scenario.yaml -f md -o report.md

# fail CI when anything high-severity is found
scenario-review review scenario.yaml --fail-on high

# list the rule catalog
scenario-review rules

# scaffold a starter scenario
scenario-review init
```

Exit codes: `0` no findings at or above the `--fail-on` threshold (default `medium`),
`1` findings found, `2` usage/parse error.

## Scenario format (YAML)

```yaml
id: store-checkout
title: Store checkout with discount codes
stack: python
prompt: >
  Implement checkout() that applies a discount code and charges the total.
expected_behavior: >
  Returns the final amount. Discount codes are single-use per email.
constraints: >
  Reject expired codes. Keep the reference implementation dependency-free.
reference_solution: |
  def checkout(cart, code, email):
      ...
```

All fields except `id`, `title`, and `prompt` are optional. `reference_solution` is what
the rules inspect for bad practices and edge cases; `prompt`/`expected_behavior`/
`constraints` are scanned for logical flaws and testability gaps.

## The rubric

Five dimensions, each scored 1.0–5.0 (5.0 = clean). Penalties are severity-weighted and
taper (the first `critical` finding hurts more than the fifth `info` note), so a report
with one critical issue never scores the same as a report with ten cosmetic ones.

| Dimension            | Detects                                                      |
| -------------------- | ----------------------------------------------------------- |
| Clarity              | undefined terms, hedge words, "as appropriate" dependencies |
| Correctness          | contradictions, off-by-one traps, unverifiable criteria, bad practices |
| Edge-case coverage   | empty input, nulls, float equality, concurrency, retries, timezones, unicode |
| Safety               | eval/exec, SQL injection, secrets, shell=True, unsafe pickle, missing timeouts |
| Testability          | missing example inputs, missing golden expectations, hidden env deps |

## Rule catalog

| Rule   | Name                        | Category      | Default severity |
| ------ | --------------------------- | ------------- | ---------------- |
| LF-001 | UndefinedTermsRule          | clarity       | low              |
| LF-002 | ContradictoryRequirementsRule | correctness  | medium           |
| LF-003 | UnverifiableCriteriaRule    | correctness   | low              |
| LF-004 | OffByOneBoundaryRule        | edge-case     | low              |
| LF-005 | EmptyInputSemanticsRule     | edge-case     | medium           |
| LF-006 | TimezoneNaiveDateTimeRule   | edge-case     | medium           |
| BP-001 | EvalExecRule                | safety        | high             |
| BP-002 | SqlInterpolationRule        | safety        | high             |
| BP-003 | HardcodedSecretRule         | safety        | high             |
| BP-004 | BroadExceptRule             | correctness   | medium           |
| BP-005 | SwallowedExceptionRule      | correctness   | high             |
| BP-006 | MutableDefaultArgsRule      | correctness   | medium           |
| BP-007 | PrintAsLoggingRule          | testability   | low              |
| BP-008 | ShellTrueRule               | safety        | medium           |
| BP-009 | UnsafePickleRule            | safety        | medium           |
| EC-001 | FloatEqualityRule           | correctness   | medium           |
| EC-002 | NullHandlingRule            | edge-case     | medium           |
| EC-003 | ConcurrencyLockRule         | edge-case     | medium           |
| EC-004 | UnboundedRetriesRule        | edge-case     | medium           |
| EC-005 | IdempotencyRetryRule        | edge-case     | medium           |
| EC-006 | LargeInputRule              | edge-case     | low              |
| EC-007 | UnicodeEncodingRule         | edge-case     | low              |
| EC-008 | ExternalCallTimeoutRule     | edge-case     | high             |
| EC-009 | DataShapeValidationRule     | testability   | low              |
| TB-001 | MissingExampleInputsRule    | testability   | medium           |
| TB-002 | GoldenExpectationRule       | testability   | medium           |
| TB-003 | VagueAcceptanceVerbsRule    | testability   | low              |
| TB-004 | HiddenEnvironmentDepsRule   | testability   | medium           |

Rules are **symptom-based heuristics, not proofs**: they flag patterns worth a human
look, and every finding ships with the exact evidence snippet that triggered it plus a
concrete fix suggestion. That is deliberate — an automated reviewer that hallucinates
authority is worse than a checklist that says "verify".

## Architecture

```
scenario.yaml (YAML)
      │
      ▼
Scenario.from_yaml()
      │
      ▼
ReviewEngine.run()  ──►  ReviewRule.check(scenario, ctx)  for each of 28 rules
      │                       │ (LF-*, BP-*, EC-*, TB-*)
      ▼
ReviewReport(issues, severity counts, category counts)
      │
      ├── scoring.compute_dimension_scores()  → 5 rubric dimensions
      ├── scoring.summarize()                 → verdict + top findings
      └── cli formats                         → table | json | markdown
```

Extending the engine is one file: subclass `ReviewRule`, give it a `rule_id`, declare a
default severity, and add it to the registry in `scenario_review.rules` — nothing else
changes.

## Development

```bash
pip install -e ".[dev]"
pytest                              # full suite
pytest --cov=scenario_review        # with coverage
scenario-review rules               # sanity: 28 rules registered
```

## Project layout

```
src/scenario_review/
├── models.py          Scenario / Issue / Severity / ReviewReport + YAML (de)serialization
├── scoring.py         rubric dimension scores + verdict summary
├── engine.py          ReviewEngine orchestration (rules → issues → report)
├── cli.py             scenario-review CLI (table/json/md output, --fail-on gates)
└── rules/
    ├── base.py        ReviewRule ABC + ReviewContext
    ├── logical_flaws.py   LF-001 .. LF-006
    ├── bad_practices.py   BP-001 .. BP-009
    ├── edge_cases.py      EC-001 .. EC-009
    └── testability.py     TB-001 .. TB-004
examples/scenarios/     flawed / partially flawed / clean showcase scenarios
tests/                  pytest suite incl. golden regression on the examples
```

## License

MIT — see [LICENSE](LICENSE).