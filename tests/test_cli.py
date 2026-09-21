"""CLI tests: subcommands, exit codes, output formats."""

from __future__ import annotations

import json
import subprocess
import sys

from scenario_review.cli import main


def run_cli(*argv):
    return main(list(argv))


def test_review_table_on_flawed(flawed_checkout_path, capsys):
    code = run_cli("review", str(flawed_checkout_path))
    out = capsys.readouterr().out
    assert code == 1
    assert "flawed-checkout" in out or "Store checkout" in out
    assert "Score:" in out


def test_review_json(flawed_checkout_path, capsys):
    code = run_cli("review", str(flawed_checkout_path), "-f", "json")
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["scenario"]["id"] == "flawed-checkout"
    assert payload["totals"]["high"] >= 1


def test_review_markdown(flawed_checkout_path, capsys):
    code = run_cli("review", str(flawed_checkout_path), "-f", "md")
    out = capsys.readouterr().out
    assert code == 1
    assert "## Verdict" in out
    assert "## Findings" in out


def test_review_clean_passes_default_threshold(clean_scenario_path):
    assert run_cli("review", str(clean_scenario_path)) == 0


def test_fail_on_none_hides_findings(flawed_checkout_path):
    assert run_cli("review", str(flawed_checkout_path), "--fail-on", "info") == 1
    assert run_cli("review", str(flawed_checkout_path), "--fail-on", "medium") == 1


def test_review_missing_file(tmp_path, capsys):
    code = run_cli("review", str(tmp_path / "missing.yaml"))
    assert code == 2
    assert "error" in capsys.readouterr().err


def test_rules_subcommand(capsys):
    assert run_cli("rules") == 0
    out = capsys.readouterr().out
    assert "LF-001" in out and "BP-003" in out
    assert "28 rule(s)" in out


def test_rules_filter(capsys):
    assert run_cli("rules", "--category", "safety") == 0
    out = capsys.readouterr().out
    assert "BP-001" in out
    assert "TB-001" not in out


def test_init_scaffolds(tmp_path, capsys):
    target = tmp_path / "proj"
    assert run_cli("init", str(target)) == 0
    assert (target / "scenario.yaml").exists()
    assert "Gener" not in capsys.readouterr().out


def test_entrypoint_installed():
    env = {"PATH": sys.prefix + "/bin:" + __import__("os").environ.get("PATH", "")}
    result = subprocess.run(
        ["scenario-review", "--version"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0
    assert "scenario-review" in result.stdout