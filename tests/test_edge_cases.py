"""EC-* rule tests."""

from __future__ import annotations

import pytest

from scenario_review.rules.base import ReviewContext
from scenario_review.rules.edge_cases import (
    ConcurrencyLockRule,
    DataShapeValidationRule,
    ExternalCallTimeoutRule,
    FloatEqualityRule,
    IdempotencyRetryRule,
    LargeInputRule,
    NullHandlingRule,
    UnicodeEncodingRule,
    UnboundedRetriesRule,
)


@pytest.mark.parametrize(
    "code,rule_cls",
    [
        ("if total == 0.0:\n    pass\n", FloatEqualityRule),
        ("price = amount * 0.1\n", FloatEqualityRule),
        ("row = data['name']\nprint(row)\n", NullHandlingRule),
        ("data = parser.parse_response()\nprint(data['id'])\n", NullHandlingRule),
        ("with ThreadPoolExecutor(4) as ex:\n    [ex.submit(job, i) for i in range(10)]\nstock[i] -= 1\n", ConcurrencyLockRule),
        ("while True:\n    r = requests.get(url)\n    print(r.text)\n", UnboundedRetriesRule),
        ("from webhook import handle\nfor event in queue.poll():\n    process(event)\n", IdempotencyRetryRule),
        ("rows = open('t.csv').readlines()\nfor r in rows:\n    print(r)\n", LargeInputRule),
        ("text = open('notes.txt', 'w').write(body)\n", UnicodeEncodingRule),
        ("payload = requests.get('http://api.example/x').text\n", ExternalCallTimeoutRule),
        ("data = json.loads(resp)\nreturn data['items']\n", DataShapeValidationRule),
    ],
)
def test_edge_cases_flagged(scenario_factory, code, rule_cls):
    scenario = scenario_factory(
        reference_solution=code,
        prompt="Implement the described behavior.",
        expected_behavior="",
        constraints="",
    )
    assert rule_cls().check(scenario, ReviewContext(scenario))


@pytest.mark.parametrize(
    "code,rule_cls",
    [
        ("if math.isclose(total, 0.0, rel_tol=1e-9):\n    pass\n", FloatEqualityRule),
        ("row = data.get('name') or 'unknown'\n", NullHandlingRule),
        ("with ThreadPoolExecutor(4) as ex:\n    [ex.submit(job, i) for i in range(10)]\n", ConcurrencyLockRule),
        ("for attempt in range(5):\n    try:\n        r = requests.get(url, timeout=5)\n        break\n    except RequestException:\n        time.sleep(2 ** attempt)\n", UnboundedRetriesRule),
        ("for event in queue.poll():\n    if event.id in seen:\n        continue\n    seen.add(event.id)\n    process(event)\n", IdempotencyRetryRule),
        ("with pd.read_csv('t.csv', chunksize=1000) as reader:\n    pass\n", LargeInputRule),
        ("text = open('notes.txt', encoding='utf-8').read()\n", UnicodeEncodingRule),
        ("payload = requests.get('http://api.example/x', timeout=(3, 10)).text\n", ExternalCallTimeoutRule),
        ("data = parse_with_schema(resp, OrderSchema)\n", DataShapeValidationRule),
    ],
)
def test_edge_cases_clean(scenario_factory, code, rule_cls):
    scenario = scenario_factory(reference_solution=code)
    assert not rule_cls().check(scenario, ReviewContext(scenario))