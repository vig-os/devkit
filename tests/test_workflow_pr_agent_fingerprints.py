"""Workflow-shape tests: commit-checks must guard the PR body for agent fingerprints.

Issue #1052: the ``check-pr-agent-fingerprints`` entry point exists in
``vig_utils`` but no workflow invoked it — a guard nothing calls is not a guard.
After #1026 the ``commit-checks`` job already validates the PR **title** via
``validate-commit-range --title``; this entry point's unique coverage is the PR
**body** (it reads ``PR_TITLE``/``PR_BODY`` from env and greps them against
``.github/agent-blocklist.toml``). The body is attacker-controlled text visible
in the UI and notifications even though it never enters git history.

The fix wires ``check-pr-agent-fingerprints`` into the ``commit-checks`` job of
both ci.yml copies as a cheap defense-in-depth step, passing ``PR_TITLE`` and
``PR_BODY`` via ``env:`` (never interpolated into the ``run:`` script) so the
attacker-controlled body cannot inject shell.

These assertions pin that invariant for both copies: the devkit's own workflow
and the independent scaffold copy shipped to consumers.

Refs: #1052
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

# Repository root (tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parent.parent

ENTRY_POINT = "check-pr-agent-fingerprints"

# Both ci.yml copies are independent (not manifest-synced); each must guard the
# PR body. The devkit's own workflow and the scaffold copy under assets/workspace/.
CI_WORKFLOWS = [
    REPO_ROOT / ".github" / "workflows" / "ci.yml",
    REPO_ROOT / "assets" / "workspace" / ".github" / "workflows" / "ci.yml",
]


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _fingerprint_step(steps: list[dict]) -> dict | None:
    for step in steps:
        if ENTRY_POINT in str(step.get("run", "")):
            return step
    return None


@pytest.mark.parametrize(
    "path", CI_WORKFLOWS, ids=lambda p: str(p.relative_to(REPO_ROOT))
)
def test_commit_checks_guards_pr_body(path: Path) -> None:
    """commit-checks runs check-pr-agent-fingerprints with PR_TITLE/PR_BODY via env."""
    workflow = _load(path)
    assert "commit-checks" in workflow["jobs"], f"{path} has no `commit-checks` job"
    steps = workflow["jobs"]["commit-checks"]["steps"]

    step = _fingerprint_step(steps)
    assert step is not None, (
        f"{path} commit-checks job must run `{ENTRY_POINT}` to guard the PR body "
        f"(#1052)"
    )

    env = step.get("env", {})
    # Attacker-controlled text must arrive via env, never inline in the run script.
    assert env.get("PR_BODY") == "${{ github.event.pull_request.body }}", (
        f"{path} `{ENTRY_POINT}` step must pass PR_BODY via env from "
        f"github.event.pull_request.body; found {env.get('PR_BODY')!r}"
    )
    assert env.get("PR_TITLE") == "${{ github.event.pull_request.title }}", (
        f"{path} `{ENTRY_POINT}` step must pass PR_TITLE via env from "
        f"github.event.pull_request.title; found {env.get('PR_TITLE')!r}"
    )
    # Injection safety: the attacker-controlled values must not be interpolated
    # into the shell command text.
    run = str(step.get("run", ""))
    assert "github.event.pull_request.body" not in run, (
        f"{path} `{ENTRY_POINT}` step must not interpolate the PR body into the "
        f"run script — pass it via env only"
    )
