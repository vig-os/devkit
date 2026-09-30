"""Workflow-shape tests: sync-issues watermark save gating.

Issue #1757: the `Save sync state` step in `sync-issues.yml` saved the incremental
sync watermark with `if: always()`, advancing the cutoff even when the `Commit and
push changes via API` step failed. The next run would then sync from the advanced
cutoff and silently drop any issues/PRs whose files were not pushed.

The fix gates the watermark save on the sync having succeeded AND the commit not
having failed:

    if: ${{ steps.sync.outcome == 'success' && steps.commit.outcome != 'failure' }}

When the commit step is skipped (nothing to commit), its outcome is `skipped`, which
is not `failure`, so the save still runs — which is correct. A failed push then
leaves the previous cutoff in place and the next run retries the same delta,
self-healing.

These assertions pin the gated save-step shape for both copies: the devkit's own
workflow and the scaffold template shipped to consumers.

Refs: #1757
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.workflow_scaffold import (
    REPO_ROOT,
    both_copies,
    load_workflow,
    step_by_id,
    step_by_name,
    steps_of_job,
)

if TYPE_CHECKING:
    from pathlib import Path

# Both copies: devkit's own sync-issues.yml and the scaffold template.
SYNC_WORKFLOWS = both_copies("sync-issues.yml")


@pytest.mark.parametrize(
    "path", SYNC_WORKFLOWS, ids=lambda p: str(p.relative_to(REPO_ROOT))
)
def test_sync_state_save_gated_on_successful_push(path: Path) -> None:
    """The watermark must only be saved when the delta was actually pushed.

    The `Save sync state` step must not run with `if: always()`. Instead it must
    be gated on both:
    - The sync step having succeeded (steps.sync.outcome == 'success')
    - The commit step not having failed (steps.commit.outcome != 'failure')

    A skipped commit (when there are no changes) is legitimate, so the condition
    must allow skipped outcomes (which is achieved by checking != 'failure').
    """
    assert path.is_file(), f"{path} must exist"
    steps = steps_of_job(load_workflow(path), "sync")

    # Precondition: the required step ids must exist
    sync_step = step_by_id(steps, "sync")
    commit_step = step_by_id(steps, "commit")
    assert sync_step is not None, "sync step must have id='sync'"
    assert commit_step is not None, "commit step must have id='commit'"

    # Get the Save sync state step
    save_step = step_by_name(steps, "Save sync state")

    # Assert that it does NOT use if: always()
    if_condition = str(save_step.get("if", ""))
    assert if_condition != "always()", (
        f"Save sync state step must not use `if: always()` (prevents silent data loss); "
        f"found: {if_condition!r}"
    )

    # Assert that it has the correct gating condition
    assert "steps.sync.outcome == 'success'" in if_condition, (
        "Save sync state must gate on sync having succeeded"
    )
    assert "steps.commit.outcome != 'failure'" in if_condition, (
        "Save sync state must gate on commit not having failed "
        "(allows skipped when nothing to commit)"
    )
