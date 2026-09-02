"""Workflow-shape tests: superseded CI runs are cancelled per ref (#1602).

Issue #1602: ``ci.yml`` carried no ``concurrency`` block, so a force-push or a
rapid follow-up push left the superseded run's every lane running to completion
for a commit that no longer matters. On a hosted runner that is wasted billed
minutes; on a self-hosted consumer with a small fixed slot pool the stale run
occupies the slots and the replacement run queues behind its own predecessor.

Both copies are pinned, because they are separate render paths — devkit's own
image-building CI and the mode-aware scaffold consumers receive — and #1414 is
the standing proof that a fix landing in one copy only is the likely failure.

The cancel condition is ``github.event_name != 'push'`` rather than a bare
``true``: neither copy triggers on ``push`` today, so the guard is inert, but a
deploy gate that keys on the exact-commit CI run must stay satisfiable if a
push trigger is ever added. It is deliberately NOT ``== 'pull_request'`` —
that would also exempt ``workflow_dispatch``, where a dispatched re-test
superseding the previous one is the wanted behaviour.

Cancellation composes with the existing gate semantics rather than fighting
them: the summary job is ``if: always()`` and trips on ``cancelled`` for every
needed job (#1371/#1414, pinned in ``tests/test_workflow_summary_gate.py``), so
a cancelled superseded run cannot green the required check; and the release-PR
CI gate evaluates only the latest run per check name (#1522, pinned in
``tests/test_ci_green_gate.py``), so a superseded run's entries cannot refuse a
branch that is actually green.

Refs: #1602
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.workflow_scaffold import WORKSPACE, load_workflow

# Repository root (tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parent.parent

# copy id -> workflow path. Separate render paths, identical doctrine.
CI_COPIES: dict[str, Path] = {
    "devkit": REPO_ROOT / ".github" / "workflows" / "ci.yml",
    "scaffold": WORKSPACE / ".github" / "workflows" / "ci.yml",
}

# Per-workflow, per-ref: a PR's superseded run is cancelled, while distinct refs
# (another PR, a dispatch on another branch) stay independent.
GROUP = "ci-${{ github.workflow }}-${{ github.ref }}"

# Cancel everything except a push run (see module docstring).
CANCEL_IN_PROGRESS = "${{ github.event_name != 'push' }}"


def _concurrency(copy: str) -> dict:
    block = load_workflow(CI_COPIES[copy]).get("concurrency")
    assert isinstance(block, dict), (
        f"{copy} ci.yml must declare a workflow-level concurrency block (#1602)"
    )
    return block


@pytest.mark.parametrize("copy", sorted(CI_COPIES))
def test_ci_groups_concurrency_per_ref(copy: str) -> None:
    """The group is per-workflow and per-ref, so only a true supersession collides."""
    group = _concurrency(copy).get("group", "")
    assert "${{ github.ref }}" in group, (
        f"{copy}: the concurrency group must be per-ref so distinct refs "
        "(other PRs, dispatches on other branches) stay independent"
    )
    assert group == GROUP, f"{copy}: expected group {GROUP!r}, got {group!r}"


@pytest.mark.parametrize("copy", sorted(CI_COPIES))
def test_ci_cancels_superseded_runs(copy: str) -> None:
    """A newer run on the same ref cancels the superseded one — except on push."""
    cancel = _concurrency(copy).get("cancel-in-progress")
    assert cancel == CANCEL_IN_PROGRESS, (
        f"{copy}: expected cancel-in-progress {CANCEL_IN_PROGRESS!r}, got "
        f"{cancel!r} — superseded pull_request and workflow_dispatch runs must "
        "be cancelled, while an in-flight push run must survive a newer push "
        "so a deploy gating on its exact-commit CI stays satisfiable"
    )
