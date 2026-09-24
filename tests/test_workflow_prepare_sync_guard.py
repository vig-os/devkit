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

Refs: #1680
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.workflow_scaffold import (
    REPO_ROOT,
    load_workflow,
    step_by_name,
    steps_of_job,
)

if TYPE_CHECKING:
    from pathlib import Path

DEVKIT_PREPARE = REPO_ROOT / ".github" / "workflows" / "prepare-release.yml"
SYNC_MAIN_TO_DEV = REPO_ROOT / ".github" / "workflows" / "sync-main-to-dev.yml"

COPIES = {"devkit": DEVKIT_PREPARE}

# The single expression both lanes share: sync-main-to-dev opens its PR when
# this is non-zero, prepare-release refuses while it is non-zero.
BEHIND_EXPR = "BEHIND=$(git rev-list --count origin/main ^origin/dev)"

# Step-name fragment the guard is found by.
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
