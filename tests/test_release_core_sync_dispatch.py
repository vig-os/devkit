"""Workflow-shape tests: release-core sync-issues dispatch is release-branch-pinned.

Issue #1150: a consumer's first final ``release.yml`` run timed out at finalize
because the ``sync-issues`` dispatch and its polls were under-specified:

1. ``gh workflow run sync-issues.yml`` passed no ``--ref``, so GitHub resolved
   the workflow **on the default branch** — the pre-devkit workflow until the
   first devkit release merges.
2. ``TIMEOUT=120`` was too tight even for the devkit workflow's first
   release-branch run (no cutoff cache → self-heal took > 3m).
3. Both ``gh run list`` polls omitted ``--branch``, so a concurrent scheduled
   run could be mistaken for the dispatched one.

These assertions pin the fix in the shipped ``release-core.yml``: the dispatch
is ``--ref``-pinned to the release branch, both polls are ``--branch``-filtered
to it, and the wait timeout is generous. The choreography is bash and not
unit-testable here.

Refs: #1150
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


def test_dispatch_pins_the_release_branch_ref() -> None:
    """The sync-issues dispatch runs the release branch's workflow, not the default."""
    run = _step("Trigger sync-issues")["run"]
    assert "gh workflow run sync-issues.yml" in run
    assert '--ref "release/$VERSION"' in run


def test_wait_timeout_is_generous() -> None:
    """120s was too tight even for the devkit workflow; the ceiling is raised."""
    run = _step("Wait for sync-issues")["run"]
    assert "TIMEOUT=600" in run
    assert "TIMEOUT=120" not in run


def test_polls_filter_on_the_release_branch() -> None:
    """Both the wait loop and the conclusion check filter to the dispatched run."""
    run = _step("Wait for sync-issues")["run"]
    # --branch appears on both the status poll and the conclusion poll.
    assert run.count('--branch "release/$VERSION"') >= 2
