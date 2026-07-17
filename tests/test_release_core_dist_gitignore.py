"""Workflow-shape tests: release-core commits only the non-ignored dist/ files.

Issue #1159: the finalize commit passed the whole ``dist`` directory to
``commit-action`` (``FILE_PATHS: CHANGELOG.md,dist``). ``commit-action`` walks
that directory on disk and force-adds **every** file it finds — it never
consults ``.gitignore`` — so the gitignored tsc/ncc byproducts (``dist/src/**``,
``*.tsbuildinfo``) get re-committed on every final release, defeating the
"ship only the bundle" invariant and making the sanctioned ``git rm --cached``
cleanup impossible to persist.

The fix computes the tracked-plus-untracked-but-not-ignored set under ``dist``
with ``git ls-files -co --exclude-standard`` (i.e. ``git add`` /``.gitignore``
semantics) and passes only those explicit files, so the finalize commit ships
``dist/index.js`` + ``dist/licenses.txt`` without the gitignored emit.

Refs: #1159
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO_ROOT / "assets" / "workspace" / ".github" / "workflows"


def _finalize_steps() -> list[dict]:
    workflow = yaml.safe_load(
        (WORKFLOWS / "release-core.yml").read_text(encoding="utf-8")
    )
    return workflow["jobs"]["finalize"]["steps"]


def _step(name_fragment: str) -> dict:
    frag = name_fragment.lower()
    return next(s for s in _finalize_steps() if frag in str(s.get("name", "")).lower())


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
