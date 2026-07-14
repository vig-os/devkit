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

Refs: #1034
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

# Repository root (tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parent.parent

SYNC_WORKFLOWS = [
    REPO_ROOT / ".github" / "workflows" / "sync-main-to-dev.yml",
    REPO_ROOT
    / "assets"
    / "workspace"
    / ".github"
    / "workflows"
    / "sync-main-to-dev.yml",
]


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _steps_of_job(workflow: dict, job: str) -> list[dict]:
    return workflow["jobs"][job]["steps"]


def _checkout_steps(steps: list[dict]) -> list[dict]:
    return [s for s in steps if "actions/checkout" in str(s.get("uses", ""))]


def _uses_local_action(steps: list[dict]) -> bool:
    return any(str(s.get("uses", "")).startswith("./") for s in steps)


@pytest.mark.parametrize(
    "path", SYNC_WORKFLOWS, ids=lambda p: str(p.relative_to(REPO_ROOT))
)
def test_sync_job_checkout_uses_default_ref(path: Path) -> None:
    """The sync job runs a local action, so it must check out the default ref."""
    steps = _steps_of_job(_load(path), "sync")

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
