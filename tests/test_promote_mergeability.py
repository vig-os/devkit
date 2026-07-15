"""Workflow-shape test: promote validate gates on PR mergeability.

Issue #1132: ``promote-release.yml``'s ``validate`` job verified the release PR
existed, was non-draft, approved, and CI-green — but never checked whether the
PR was actually *mergeable*. Because the sequence is ``validate → promote
(undraft, irreversible) → merge``, a PR that was BEHIND ``main`` passed
validation, the Release was undrafted, and only then did the merge fail —
leaving a half-promoted release.

This pins the fail-fast gate: the validate job's release-PR verification must
query mergeability and reject a non-mergeable PR (notably BEHIND) *before* the
promote job undrafts the Release. The bash choreography (async re-query on
UNKNOWN) is not unit-testable here.

Refs: #1132
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO_ROOT / "assets" / "workspace" / ".github" / "workflows"


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _validate_pr_step_run() -> str:
    workflow = _load(WORKFLOWS / "promote-release.yml")
    steps = workflow["jobs"]["validate"]["steps"]
    step = next(s for s in steps if s.get("name") == "Find and verify release PR")
    return step["run"]


def test_validate_queries_pr_mergeability() -> None:
    """The validate PR check fetches the PR's merge state."""
    run = _validate_pr_step_run()
    assert "mergeStateStatus" in run
    assert "mergeable" in run


def test_validate_rejects_behind_pr() -> None:
    """A BEHIND (not-up-to-date) PR is rejected before the irreversible promote."""
    run = _validate_pr_step_run()
    assert "BEHIND" in run


def test_validate_requeries_unknown_mergeability() -> None:
    """GitHub computes mergeability async, so UNKNOWN is re-queried, not trusted."""
    run = _validate_pr_step_run()
    assert "UNKNOWN" in run
