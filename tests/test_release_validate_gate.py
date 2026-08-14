"""Workflow-shape tests: the finalize-side release-PR gate (#1504).

Issue #1504: one release cycle used to cost two human approvals of the same
PR — ``release.yml``'s ``validate`` job hard-failed a final unless the release
PR was ``APPROVED``, the ``finalize`` job then pushed its own commits to the
release branch (dismissing that approval via stale-review dismissal), and
``promote-release.yml`` demanded a fresh one (#1474, #1487). The single human
approval of the cycle is now collected at promote: the finalize-side
``validate`` step gates finals on **draft + CI only**, and every
``reviewDecision`` assertion (including the #438 bot-approval fallback) is
gone from it. The promote-side gates are unchanged — that out-of-scope
boundary is pinned by ``test_promote_release.py``.

Candidates were already approval-free (#902); the draft gate for finals stays
(the operator still marks the PR ready before the final dispatch).

Refs: #1504
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.workflow_scaffold import (
    REPO_ROOT,
    WORKFLOWS,
    load_workflow,
    step_by_name,
    steps_of_job,
)

if TYPE_CHECKING:
    from pathlib import Path

# copy id -> the workflow carrying the finalize-side release-PR gate
VALIDATE_COPIES: dict[str, Path] = {
    "devkit": REPO_ROOT / ".github" / "workflows" / "release.yml",
    "scaffold": WORKFLOWS / "release-core.yml",
}
COPIES = list(VALIDATE_COPIES)


def _validate_pr_step_run(copy: str) -> str:
    """The bash body of the ``Find and verify PR`` step of the validate job."""
    workflow = load_workflow(VALIDATE_COPIES[copy])
    step = step_by_name(steps_of_job(workflow, "validate"), "Find and verify PR")
    return step["run"]


@pytest.mark.parametrize("copy", COPIES)
def test_validate_asserts_no_approval(copy: str) -> None:
    """The finalize-side gate carries no approval assertion at all.

    Not just the happy-path check: the #438 bot-approval fallback (counting
    APPROVED reviews when ``reviewDecision`` comes back empty) must be gone
    too — with a count-0 ruleset it counts zero and fails a PR that the
    platform itself would merge.
    """
    run = _validate_pr_step_run(copy)
    assert "reviewDecision" not in run
    assert "APPROVED" not in run
    assert "approv" not in run.lower()


@pytest.mark.parametrize("copy", COPIES)
def test_validate_keeps_draft_gate_for_finals(copy: str) -> None:
    """Finals still refuse a draft PR; candidates still skip that gate (#902)."""
    run = _validate_pr_step_run(copy)
    assert "isDraft" in run
    assert "still in draft" in run
    assert '"$RELEASE_KIND" = "final"' in run


@pytest.mark.parametrize("copy", COPIES)
def test_validate_keeps_ci_gate(copy: str) -> None:
    """The CI rollup check is untouched — both kinds still require green CI."""
    run = _validate_pr_step_run(copy)
    assert "statusCheckRollup" in run
    assert "failed CI checks" in run
