"""Workflow-shape tests: the sync job must not check out a non-default ref.

Issue #1034: the ``sync`` job in ``sync-main-to-dev.yml`` checked out ``ref: dev``
and then invoked a *local* composite action (``uses: ./.github/actions/...``).
GitHub resolves local actions against the **checked-out workspace**, not the
workflow's ref, so the moment ``main`` adds or renames a local action that ``dev``
does not yet have, the job dies on its first run — a bootstrap deadlock, since the
only thing that would carry the new action onto ``dev`` is the very sync PR this
workflow can no longer open.

The fix drops ``ref: dev`` so the workspace is the triggering ``main`` SHA, where
the local action is guaranteed to exist. These assertions pin that invariant for
both copies: the devkit's own workflow and the scaffold shipped to consumers.

The sync-main-to-dev workflow is the gitflow ``main -> dev`` bridge; it exists
only under the gitflow workflow model. A ``trunk`` scaffold (#1205) works
straight on ``main`` and has no long-lived ``dev`` branch, so the workflow is
copy-excluded — this suite is therefore gitflow-scoped, and a trailing test
positively asserts a trunk scaffold ships no such file.

Refs: #1034
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.workflow_scaffold import (
    REPO_ROOT,
    both_copies,
    load_workflow,
    scaffold_tree,
    steps_of_job,
)

if TYPE_CHECKING:
    from pathlib import Path

# The gitflow copies: devkit's own workflow and the scaffold shipped to
# consumers. Both are the gitflow shape (assets/workspace is the gitflow
# template); trunk is asserted separately below.
SYNC_WORKFLOWS = both_copies("sync-main-to-dev.yml")


def _checkout_steps(steps: list[dict]) -> list[dict]:
    return [s for s in steps if "actions/checkout" in str(s.get("uses", ""))]


def _uses_local_action(steps: list[dict]) -> bool:
    return any(str(s.get("uses", "")).startswith("./") for s in steps)


@pytest.mark.parametrize(
    "path", SYNC_WORKFLOWS, ids=lambda p: str(p.relative_to(REPO_ROOT))
)
def test_sync_job_checkout_uses_default_ref(path: Path) -> None:
    """The sync job runs a local action, so it must check out the default ref.

    Gitflow-scoped: the sync-main-to-dev bridge exists only under gitflow. Both
    paths are the gitflow shape (devkit's own workflow + the gitflow template).
    """
    assert path.is_file(), (
        f"{path} must ship under the gitflow model (the sync-main-to-dev bridge)"
    )
    steps = steps_of_job(load_workflow(path), "sync")

    # Precondition: this test only matters because the job runs a local action,
    # which GitHub resolves against the checked-out workspace.
    assert _uses_local_action(steps), (
        f"{path} sync job no longer uses a local action — update this test"
    )

    checkouts = _checkout_steps(steps)
    assert checkouts, f"{path} sync job must contain an actions/checkout step"
    for step in checkouts:
        assert "ref" not in step.get("with", {}), (
            "sync job must check out the default ref (the triggering main SHA), "
            "not a pinned `ref: dev`, because it runs a local composite action "
            "that only exists on the newer tree (#1034)"
        )


def test_trunk_scaffold_omits_sync_main_to_dev(tmp_path: Path) -> None:
    """A trunk scaffold ships no sync-main-to-dev.yml (#1205).

    The whole point of this suite — the ``main -> dev`` sync bridge — has no
    referent under the trunk workflow model: there is no long-lived ``dev``
    branch to sync to, so init-workspace copy-excludes the file. Positively
    assert the absence (rather than skipping) so a regression that reships the
    gitflow bridge into a trunk repo is caught.
    """
    rendered = scaffold_tree(tmp_path, "trunk")
    assert not (rendered / ".github" / "workflows" / "sync-main-to-dev.yml").exists(), (
        "trunk scaffold must not ship the gitflow sync-main-to-dev bridge"
    )
