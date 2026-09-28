"""Workflow-shape tests: prepare-release refuses while dev is behind main.

Issue #1680, following the #1676 model change. ``prepare-release`` freezes
**dev's** ``## Unreleased`` into the new version section, but ``main`` may now
carry landed-yet-unshipped changes — and their changelog entries.
``sync-main-to-dev.yml`` propagates those on every ``push: [main]``, so in the
normal case ``dev`` already has them by the time a train is cut; nothing
*enforced* that ordering. Cutting while the sync PR is still open silently
drops those entries from the frozen section and publishes a release that does
not describe changes it contains.

The guard is therefore a validate-job precondition that **refuses** (a warning
would leave the incomplete changelog to be discovered later, if ever), and it
spells the comparison exactly as ``sync-main-to-dev.yml`` spells it, so the
workflow that opens the sync PR and the workflow that demands it agree by
construction rather than by coincidence.

Both copies carry it. The consumer scaffold's gitflow topology is the same one
(``prepare-hotfix``/``promote-release`` write ``main``, ``sync-main-to-dev``
carries it back to ``dev``), so the hazard is the same. Under the trunk workflow
model it is not: releases cut from ``main`` and ``sync-main-to-dev.yml`` is
copy-excluded, so the render drops the step rather than ship a comparison
against an ``origin/dev`` that does not exist — which would fail every validate
run instead of guarding anything.

Refs: #1680
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.workflow_scaffold import (
    REPO_ROOT,
    WORKFLOWS,
    cached_tree,
    load_workflow,
    step_by_name,
    steps_of_job,
)

if TYPE_CHECKING:
    from pathlib import Path

DEVKIT_PREPARE = REPO_ROOT / ".github" / "workflows" / "prepare-release.yml"
SCAFFOLD_PREPARE = WORKFLOWS / "prepare-release.yml"
SYNC_MAIN_TO_DEV = REPO_ROOT / ".github" / "workflows" / "sync-main-to-dev.yml"

COPIES = {"devkit": DEVKIT_PREPARE, "scaffold": SCAFFOLD_PREPARE}

# The single expression both lanes share: sync-main-to-dev opens its PR when
# this is non-zero, prepare-release refuses while it is non-zero.
BEHIND_EXPR = "BEHIND=$(git rev-list --count origin/main ^origin/dev)"

# Step-name fragment the guard is found by (also what the trunk render
# anchors on to delete it).
GUARD_NAME = "behind main"


def _guard_run(path: Path) -> str:
    steps = steps_of_job(load_workflow(path), "validate")
    return str(step_by_name(steps, GUARD_NAME).get("run", ""))


@pytest.mark.parametrize("path", COPIES.values(), ids=COPIES)
class TestSyncGuard:
    def test_guard_lives_in_the_validate_job(self, path: Path) -> None:
        """A precondition, not a post-hoc discovery: it gates the whole run."""
        assert BEHIND_EXPR in _guard_run(path)

    def test_guard_refuses_rather_than_warns(self, path: Path) -> None:
        run = _guard_run(path)
        assert "exit 1" in run, "the guard must fail the run, not warn"

    def test_guard_names_the_remedy(self, path: Path) -> None:
        """Merge the open sync PR, then re-dispatch — always the same fix."""
        assert "chore/sync-main-to-dev" in _guard_run(path)

    def test_guard_fetches_both_refs_it_compares(self, path: Path) -> None:
        """The comparison reads two remote-tracking refs; fetch them first."""
        run = _guard_run(path)
        fetches = [line for line in run.splitlines() if "git fetch" in line]
        assert fetches, "the guard must fetch the refs it compares"
        assert any("main" in line and "dev" in line for line in fetches), fetches

    def test_guard_runs_before_the_summary(self, path: Path) -> None:
        steps = steps_of_job(load_workflow(path), "validate")
        names = [str(s.get("name", "")) for s in steps]
        guard = next(i for i, n in enumerate(names) if GUARD_NAME in n)
        summary = next(i for i, n in enumerate(names) if n == "Summary")
        assert guard < summary


def test_guard_matches_the_sync_workflows_own_comparison() -> None:
    """Agreement by construction: one expression, spelled identically (#1680)."""
    assert BEHIND_EXPR in SYNC_MAIN_TO_DEV.read_text(encoding="utf-8")


def test_scaffold_guard_matches_its_own_sync_workflow() -> None:
    """The scaffold ships both lanes too; they must agree there as well."""
    sync = WORKFLOWS / "sync-main-to-dev.yml"
    assert BEHIND_EXPR in sync.read_text(encoding="utf-8")


def test_trunk_render_drops_the_guard() -> None:
    """Trunk cuts from main and has no sync-main-to-dev.yml (#1205).

    Keeping the step would compare ``main`` against an ``origin/dev`` a trunk
    repo does not have, failing validate on every dispatch, and would leave
    prose naming a workflow that repo never receives (#1233).
    """
    text = (
        cached_tree("trunk") / ".github" / "workflows" / "prepare-release.yml"
    ).read_text(encoding="utf-8")
    assert GUARD_NAME not in text
    assert "origin/dev" not in text
    assert "sync-main-to-dev" not in text
