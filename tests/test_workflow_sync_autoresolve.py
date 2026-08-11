"""Workflow-shape tests: sync-main-to-dev auto-resolves doc snapshot conflicts.

Issue #1403: ``docs/issues/*.md`` and ``docs/pull-requests/*.md`` are generated
independently on ``dev`` (nightly sync-issues) and on the release branch
(release-time sync-issues), so every release produces add/add conflicts on
paths absent at the merge base — and the post-release ``main -> dev`` sync PR
opens conflicted every time.

The signed-commits ruleset (all refs, no bypass actors) forbids a plain runner
merge commit, so the workflow resolves these conflicts with a single-parent
GitHub-signed commit-action commit that aligns the sync branch's copy of each
conflicted snapshot with DEV's content: with both merge sides identical the
conflict vanishes, and dev's possibly-staler snapshot self-heals at the next
nightly sync-issues run. Any conflict outside the snapshot dirs (or a
delete/modify conflict) keeps the existing manual ``merge-conflict`` path.

These assertions pin the auto-resolve pipeline shape for both copies: devkit's
own workflow and the scaffold template shipped to consumers (intentionally
decoupled files — no manifest derives one from the other).

Refs: #1403
"""

from __future__ import annotations

import re
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

SYNC_WORKFLOWS = both_copies("sync-main-to-dev.yml")

# The resolution commit must use commit-action, SHA-pinned. Shape-checked (name
# + 40-hex pin) rather than hardcoding the SHA, so a routine Renovate pin bump
# does not red this test while an unpinned or foreign action still does.
COMMIT_ACTION_PIN_RE = re.compile(r"^vig-os/commit-action@[0-9a-f]{40}$")
EFFECTIVE_CONFLICT = (
    "steps.reverify.outputs.conflict || steps.merge-check.outputs.conflict"
)

parametrized = pytest.mark.parametrize(
    "path", SYNC_WORKFLOWS, ids=lambda p: str(p.relative_to(REPO_ROOT))
)


def _index_of(steps: list[dict], step: dict) -> int:
    return steps.index(step)


@parametrized
def test_auto_resolve_step_shape_and_order(path: Path) -> None:
    """auto-resolve runs on the pushed sync branch, before the PR opens."""
    steps = steps_of_job(load_workflow(path), "sync")

    create_branch = step_by_name(steps, "Create sync branch from main")
    auto_resolve = step_by_id(steps, "auto-resolve")
    create_pr = step_by_id(steps, "create-pr")

    # commit-action commits to the REMOTE branch, so the branch must already
    # be pushed; the PR must open only after the resolution commit landed.
    assert (
        _index_of(steps, create_branch)
        < _index_of(steps, auto_resolve)
        < _index_of(steps, create_pr)
    ), "auto-resolve must sit between branch push and PR creation"

    condition = str(auto_resolve.get("if", ""))
    assert "steps.merge-check.outputs.conflict == 'true'" in condition, (
        "auto-resolve must only run when merge-check detected a conflict"
    )

    run = str(auto_resolve.get("run", ""))
    assert "--name-only" in run, "must enumerate conflicted paths via merge-tree"
    assert "docs/issues/" in run and "docs/pull-requests/" in run, (
        "must allowlist only the generated snapshot dirs"
    )
    assert "git cat-file -e" in run, (
        "must guard delete/modify conflicts (path missing from dev)"
    )
    assert "git checkout origin/dev --" in run, (
        "must materialize dev's side of the conflicted snapshots"
    )


@parametrized
def test_signed_commit_via_commit_action(path: Path) -> None:
    """The resolution commit must be GitHub-signed (ruleset: all refs)."""
    steps = steps_of_job(load_workflow(path), "sync")
    commit = step_by_name(steps, "Commit dev-side doc snapshots")

    assert COMMIT_ACTION_PIN_RE.match(str(commit.get("uses", ""))), (
        "resolution must use a SHA-pinned commit-action (GraphQL signed commit); "
        f"found {commit.get('uses')!r}"
    )
    assert "steps.auto-resolve.outputs.eligible == 'true'" in str(
        commit.get("if", "")
    ), "commit must be gated on auto-resolve eligibility"

    env = commit.get("env", {})
    assert env.get("GH_TOKEN") == "${{ steps.commit-app-token.outputs.token }}", (
        "content commits use the COMMIT_APP identity (workflow header doctrine)"
    )
    assert env.get("TARGET_BRANCH") == "refs/heads/${{ env.SYNC_BRANCH }}", (
        "commit must target the pushed sync branch"
    )
    assert env.get("FILE_PATHS") == "${{ steps.auto-resolve.outputs.file_paths }}", (
        "commit must take exactly the conflicted paths auto-resolve emitted"
    )


@parametrized
def test_reverify_step(path: Path) -> None:
    """After the signed commit, the merge must be re-proven clean."""
    steps = steps_of_job(load_workflow(path), "sync")
    reverify = step_by_id(steps, "reverify")

    assert "steps.auto-resolve.outputs.eligible == 'true'" in str(
        reverify.get("if", "")
    ), "reverify must be gated on auto-resolve eligibility"

    run = str(reverify.get("run", ""))
    assert "git fetch origin" in run, "must refetch the sync branch after the commit"
    assert "merge-tree --write-tree" in run, "must re-run the in-memory merge probe"
    assert 'origin/${SYNC_BRANCH}"' in run, (
        "must probe origin/dev against the UPDATED sync branch, not origin/main"
    )


@parametrized
def test_effective_conflict_flag_wiring(path: Path) -> None:
    """PR body/label and auto-merge must consume the post-resolve flag."""
    steps = steps_of_job(load_workflow(path), "sync")

    create_pr = step_by_id(steps, "create-pr")
    assert (
        create_pr.get("env", {}).get("CONFLICT") == "${{ " + EFFECTIVE_CONFLICT + " }}"
    ), "Create PR must consume the effective (post-resolve) conflict flag"

    auto_merge = step_by_name(steps, "Enable auto-merge")
    assert "(" + EFFECTIVE_CONFLICT + ") != 'true'" in str(auto_merge.get("if", "")), (
        "auto-merge must be gated on the effective (post-resolve) conflict flag"
    )


def test_new_steps_identical_across_copies() -> None:
    """The decoupled copies must not drift on the auto-resolve block."""
    own, template = (steps_of_job(load_workflow(p), "sync") for p in SYNC_WORKFLOWS)
    for locate in (
        lambda steps: step_by_id(steps, "auto-resolve"),
        lambda steps: step_by_name(steps, "Commit dev-side doc snapshots"),
        lambda steps: step_by_id(steps, "reverify"),
    ):
        assert locate(own) == locate(template), (
            "auto-resolve steps must stay byte-identical across the two copies"
        )
