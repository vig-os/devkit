"""Byte-preserving reconciliation canaries for reviewer layouts (#1994)."""

import re
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
BASE = """repos:
  - repo: local
    hooks:
      - id: trailing-whitespace
        name: existing
        entry: echo
        language: system
"""
LAYOUTS = {
    "stock": (ROOT / "assets/workspace/.pre-commit-config.yaml").read_bytes(),
    "repos-not-last": (BASE + "fail_fast: false\n").encode(),
    "indent-zero": BASE.replace("\n  ", "\n", 1)
    .replace("    hooks:", "  hooks:")
    .replace("      -", "    -")
    .replace("        ", "      ")
    .encode(),
    "no-final-newline": BASE.rstrip().encode(),
    "block-scalar": BASE.replace(
        "        entry:", "        exclude: |\n          ^vendor/\n        entry:"
    ).encode(),
    "exclude-first": BASE.replace(
        "      - id:", "      - exclude: '^vendor/'\n        id:"
    ).encode(),
    "crlf": BASE.replace("\n", "\r\n").encode(),
}


def reconcile(path, enabled, env=None):
    return subprocess.run(
        [
            "typst-scaffold",
            str(path.parent),
            str(ROOT / "assets/docs-hooks.json"),
            str(enabled).lower(),
        ],
        capture_output=True,
        text=True,
        env=env,
    )


def lint_findings(path):
    """Compare actual strict findings by rule/message, excluding locations."""
    result = subprocess.run(
        [
            "yamllint",
            "--strict",
            "-f",
            "parsable",
            "-c",
            str(ROOT / "assets/workspace/.yamllint"),
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode in (0, 1, 2), result.stderr
    findings = set()
    for line in result.stdout.splitlines():
        match = re.fullmatch(
            r".*?:\d+:\d+: \[(?:warning|error)\] (.*) \(([^()]*)\)", line
        )
        assert match, line
        findings.add((match[2], match[1]))
    return findings


@pytest.mark.parametrize("layout", LAYOUTS)
def test_layout_on_off_round_trip_and_real_parsers(tmp_path, layout):
    path = tmp_path / ".pre-commit-config.yaml"
    original = LAYOUTS[layout]
    path.write_bytes(original)
    before = lint_findings(path)
    result = reconcile(path, True)
    assert result.returncode == 0, result.stderr
    checked = subprocess.run(
        ["prek", "validate-config", str(path)], capture_output=True, text=True
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert lint_findings(path) <= before
    on = path.read_bytes()
    assert on.endswith(b"\n") == original.endswith(b"\n")
    assert (b"\r\n" in on) == (b"\r\n" in original)
    assert original.splitlines()[1] in on.splitlines()
    doc = yaml.safe_load(path.read_bytes())
    assert (
        len([h for r in doc["repos"] for h in r["hooks"] if h["id"] == "typst-compile"])
        == 1
    )
    on = path.read_bytes()
    assert reconcile(path, True).returncode == 0
    assert path.read_bytes() == on
    assert reconcile(path, False).returncode == 0
    assert path.read_bytes() == original


@pytest.mark.parametrize("failure_call", [2, 3])
def test_validation_failure_restores_original(tmp_path, monkeypatch, failure_call):
    from vig_utils import typst_scaffold

    path = tmp_path / ".pre-commit-config.yaml"
    original = LAYOUTS["crlf"]
    path.write_bytes(original)
    monkeypatch.setattr(
        "sys.argv",
        ["typst-scaffold", str(tmp_path), str(ROOT / "assets/docs-hooks.json"), "true"],
    )
    calls = []

    def reject_candidate(*args, **kwargs):
        calls.append(Path(args[0][-1]).read_bytes())
        return subprocess.CompletedProcess(
            args, int(len(calls) == failure_call), "", "parser rejected candidate"
        )

    monkeypatch.setattr(subprocess, "run", reject_candidate)
    assert typst_scaffold.main() == 1
    assert path.read_bytes() == original
    assert len(calls) == failure_call and calls[-1] != original


def test_unsupported_flow_layout_is_unchanged_with_manual_notice(tmp_path):
    path = tmp_path / ".pre-commit-config.yaml"
    original = (
        b"repos: [{repo: local, hooks: [{id: x, entry: echo, language: system}]}]\n"
    )
    path.write_bytes(original)
    result = reconcile(path, True)
    assert result.returncode == 1
    assert "by hand" in result.stderr
    assert path.read_bytes() == original


def test_existing_handwritten_hooks_are_not_duplicated(tmp_path):
    path = tmp_path / ".pre-commit-config.yaml"
    original = (
        BASE
        + "      - id: typst-compile\n        name: existing\n        entry: echo\n        language: system\n      - id: typstyle\n        name: existing\n        entry: echo\n        language: system\n"
    )
    path.write_text(original)
    result = reconcile(path, True)
    assert result.returncode == 0, result.stderr
    hooks = [
        h["id"] for r in yaml.safe_load(path.read_bytes())["repos"] for h in r["hooks"]
    ]
    assert hooks.count("typst-compile") == 1
    assert "typstyle-check" not in hooks
    assert "notice" in result.stderr.lower()
    assert reconcile(path, False).returncode == 0
    assert path.read_text() == original


def test_mixed_newlines_are_rejected_without_rewriting(tmp_path):
    path = tmp_path / ".pre-commit-config.yaml"
    original = BASE.replace("repos:\n", "repos:\r\n").encode()
    path.write_bytes(original)
    result = reconcile(path, True)
    assert result.returncode == 1
    assert "by hand" in result.stderr
    assert path.read_bytes() == original
