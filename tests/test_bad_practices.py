"""BP-* rule tests."""

from __future__ import annotations

import pytest

from scenario_review.rules.bad_practices import (
    BroadExceptRule,
    EvalExecRule,
    HardcodedSecretRule,
    MutableDefaultArgsRule,
    PrintAsLoggingRule,
    ShellTrueRule,
    SqlInterpolationRule,
    SwallowedExceptionRule,
    UnsafePickleRule,
)
from scenario_review.rules.base import ReviewContext


@pytest.mark.parametrize(
    "code,rule_cls",
    [
        ("def f(x):\n    return eval(x)\n", EvalExecRule),
        ("def f(x):\n    exec(x)\n", EvalExecRule),
        ("def f(a, b):\n    conn.execute(f\"SELECT * FROM t WHERE id = {a}\")\n", SqlInterpolationRule),
        ("api_key = '[REDACTED]'\n", HardcodedSecretRule),
        ("try:\n    x()\nexcept:\n    pass\n", BroadExceptRule),
        ("try:\n    x()\nexcept Exception as e:\n    pass\n", BroadExceptRule),
        ("try:\n    x()\nexcept KeyError:\n    pass\n", SwallowedExceptionRule),
        ("def f(items=[]):\n    return len(items)\n", MutableDefaultArgsRule),
        ("def f(item):\n    print(item)\n", PrintAsLoggingRule),
        ("subprocess.run(f\"ls {path}\", shell=True)\n", ShellTrueRule),
        ("os.system('rm -rf /tmp/x')\n", ShellTrueRule),
        ("data = pickle.load(open('x.pkl', 'rb'))\n", UnsafePickleRule),
    ],
)
def test_bad_practices_flagged(scenario_factory, code, rule_cls):
    scenario = scenario_factory(reference_solution=code, expected_behavior="", constraints="")
    assert rule_cls().check(scenario, ReviewContext(scenario))


@pytest.mark.parametrize(
    "code,rule_cls",
    [
        ("def f(x):\n    return ast.literal_eval(x)\n", EvalExecRule),
        ("def f(a, b):\n    conn.execute(sql, (a, b))\n", SqlInterpolationRule),
        ("def f(api_key):\n    return api_key\n", HardcodedSecretRule),
        ("try:\n    x()\nexcept ValueError as e:\n    logger.warning(e)\n", BroadExceptRule),
        ("def f(items=None):\n    items = items or []\n    return len(items)\n", MutableDefaultArgsRule),
        ("def f(item):\n    logger.info('item %s', item)\n", PrintAsLoggingRule),
        ("subprocess.run([\"ls\", path])\n", ShellTrueRule),
        ("data = json.load(open('x.json', encoding='utf-8'))\n", UnsafePickleRule),
    ],
)
def test_clean_code_not_flagged(scenario_factory, code, rule_cls):
    scenario = scenario_factory(reference_solution=code)
    assert not rule_cls().check(scenario, ReviewContext(scenario))