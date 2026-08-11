"""Workflow-shape tests: the scaffold ``release-core.yml`` finalize job.

Two pinned incidents share this file (merged from the former
``test_release_core_dist_gitignore.py`` / ``test_release_core_sync_dispatch.py``):

Issue #1159: the finalize commit passed the whole ``dist`` directory to
``commit-action`` (``FILE_PATHS: CHANGELOG.md,dist``). ``commit-action`` walks
that directory on disk and force-adds **every** file it finds — it never
consults ``.gitignore`` — so the gitignored tsc/ncc byproducts (``dist/src/**``,
``*.tsbuildinfo``) got re-committed on every final release. The fix computes the
tracked-plus-untracked-but-not-ignored set under ``dist`` with
``git ls-files -co --exclude-standard`` and passes only those explicit files.

Issue #1150: a consumer's first final ``release.yml`` run timed out at finalize
because the ``sync-issues`` dispatch and its polls were under-specified — no
``--ref`` (so GitHub resolved the workflow on the default branch), a
too-tight wait timeout, and unfiltered ``gh run list`` polls that could mistake
a concurrent scheduled run for the dispatched one. The fix pins the dispatch to
the release branch, filters both polls to it, and raises the wait ceiling.

The choreography is bash and not unit-testable here.

Refs: #1150, #1159
"""

from __future__ import annotations

import re

from tests.workflow_scaffold import WORKFLOWS, load_workflow


def _finalize_steps() -> list[dict]:
    workflow = load_workflow(WORKFLOWS / "release-core.yml")
    return workflow["jobs"]["finalize"]["steps"]


def _step(name_fragment: str) -> dict:
    frag = name_fragment.lower()
    return next(s for s in _finalize_steps() if frag in str(s.get("name", "")).lower())


# ── dist/.gitignore semantics (#1159) ─────────────────────────────────────────


def test_finalize_does_not_commit_the_whole_dist_dir() -> None:
    """FILE_PATHS must not pass the bare ``dist`` directory (force-adds ignored)."""
    file_paths = _step("Commit and push finalization")["env"]["FILE_PATHS"]
    assert ",dist'" not in file_paths
    assert "'CHANGELOG.md,dist'" not in file_paths


def test_build_step_computes_non_ignored_dist_paths() -> None:
    """The artifact build honors .gitignore when listing dist/ files to commit."""
    run = _step("Build release artifact")["run"]
    assert "git ls-files -co --exclude-standard -- dist" in run
    # The list is exposed as a step output for the commit step to consume.
    assert "dist_paths=" in run
    assert '>> "$GITHUB_OUTPUT"' in run


def test_file_paths_reference_the_computed_dist_paths() -> None:
    """FILE_PATHS threads the computed, gitignore-respecting dist path list."""
    file_paths = _step("Commit and push finalization")["env"]["FILE_PATHS"]
    assert "dist_paths" in file_paths
    # CHANGELOG.md is still committed in both the bundle and no-bundle branches.
    assert "CHANGELOG.md" in file_paths


# ── sync-issues dispatch pinning (#1150) ──────────────────────────────────────


def test_dispatch_pins_the_release_branch_ref() -> None:
    """The sync-issues dispatch runs the release branch's workflow, not the default."""
    run = _step("Trigger sync-issues")["run"]
    assert "gh workflow run sync-issues.yml" in run
    assert '--ref "release/$VERSION"' in run


def test_wait_timeout_is_generous() -> None:
    """120s was too tight even for the devkit workflow; the ceiling stays raised."""
    run = _step("Wait for sync-issues")["run"]
    match = re.search(r"TIMEOUT=(\d+)", run)
    assert match, "the wait loop must declare a TIMEOUT"
    assert int(match.group(1)) >= 600, (
        f"sync-issues wait TIMEOUT={match.group(1)} regressed below the 600s "
        "floor a first release-branch run needs (#1150)"
    )


def test_polls_filter_on_the_release_branch() -> None:
    """Both the wait loop and the conclusion check filter to the dispatched run."""
    run = _step("Wait for sync-issues")["run"]
    # --branch appears on both the status poll and the conclusion poll.
    assert run.count('--branch "release/$VERSION"') >= 2
