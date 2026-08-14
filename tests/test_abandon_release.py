"""Workflow-shape tests: the abandon-release rejection path, both copies.

#1504 added ``abandon-release.yml`` to devkit as the draft-only rejection path
at promote time; #1511 ships the consumer variant in the scaffold. Both copies
carry the same server-side guards (published release ⇒ hard refusal, tag
deletion only when no GitHub Release remains attached, fail-closed leftovers
sweep). The scaffold copy additionally threads ``DEVKIT_TAG_PREFIX`` through a
leading ``resolve-toolchain`` job — consumers may tag ``vX.Y.Z`` (#1044) — and
shares the consumer promote lane (``publish-release``) instead of devkit's
image lane (``publish-image``).

Refs: #1511
"""

from __future__ import annotations

import pytest

from tests.workflow_scaffold import (
    both_copies,
    jobs,
    load_workflow,
    needs_of,
    run_text_of_job,
    step_by_name,
    steps_of_job,
)

DEVKIT_COPY, SCAFFOLD_COPY = both_copies("abandon-release.yml")
COPIES = {"devkit": DEVKIT_COPY, "scaffold": SCAFFOLD_COPY}


def test_scaffold_ships_abandon_release() -> None:
    """The consumer scaffold ships the workflow the synced recipe dispatches."""
    assert SCAFFOLD_COPY.is_file(), (
        "assets/workspace/.github/workflows/abandon-release.yml missing — the "
        "synced `just abandon-release` recipe would dispatch a nonexistent "
        "workflow"
    )


@pytest.mark.parametrize("copy", COPIES)
def test_published_release_is_hard_refused(copy: str) -> None:
    """A published release must never be abandoned (tombstone protection)."""
    doc = load_workflow(COPIES[copy])
    validate_run = run_text_of_job(jobs(doc)["validate"])
    assert '"$IS_DRAFT" != "true"' in validate_run
    assert "tombstone" in validate_run


@pytest.mark.parametrize("copy", COPIES)
def test_tag_deleted_only_without_attached_release(copy: str) -> None:
    """Tag deletion is refused while any GitHub Release still points at it."""
    doc = load_workflow(COPIES[copy])
    abandon_run = run_text_of_job(jobs(doc)["abandon"])
    assert "refusing to delete the tag" in abandon_run
    assert "git/refs/tags/" in abandon_run


@pytest.mark.parametrize("copy", COPIES)
def test_abandon_deletes_as_the_release_app(copy: str) -> None:
    """Ref/release deletion runs as the Release App (tag-ruleset bypass)."""
    doc = load_workflow(COPIES[copy])
    steps = steps_of_job(doc, "abandon")
    token_step = next(
        s for s in steps if "create-github-app-token" in str(s.get("uses", ""))
    )
    assert "RELEASE_APP_CLIENT_ID" in str(token_step["with"]["client-id"])
    assert "RELEASE_APP_PRIVATE_KEY" in str(token_step["with"]["private-key"])


@pytest.mark.parametrize("copy", COPIES)
def test_abandon_fails_closed_on_leftovers(copy: str) -> None:
    """The final sweep must fail the run if anything abandoned survives."""
    doc = load_workflow(COPIES[copy])
    abandon_run = run_text_of_job(jobs(doc)["abandon"])
    assert "abandon incomplete" in abandon_run


def test_concurrency_lanes_differ_by_copy() -> None:
    """Devkit shares the image promote lane; consumers the release lane."""
    assert load_workflow(DEVKIT_COPY)["concurrency"]["group"] == "publish-image"
    assert load_workflow(SCAFFOLD_COPY)["concurrency"]["group"] == "publish-release"


def test_scaffold_resolve_job_exposes_tag_prefix() -> None:
    """The scaffold copy resolves DEVKIT_TAG_PREFIX before acting on tags."""
    doc = load_workflow(SCAFFOLD_COPY)
    resolve = jobs(doc)["resolve-toolchain"]
    assert "tag-prefix" in resolve["outputs"]
    assert "resolve-toolchain" in needs_of(jobs(doc)["validate"])
    assert "resolve-toolchain" in needs_of(jobs(doc)["abandon"])


@pytest.mark.parametrize("job", ["validate", "abandon"])
def test_scaffold_threads_tag_prefix_into_tag_operations(job: str) -> None:
    """Release lookup and tag deletion use the composed ``<prefix>X.Y.Z`` tag.

    The release branch and the ``version`` input stay bare — only the git tag
    and its GitHub Release carry the prefix (#1044).
    """
    doc = load_workflow(SCAFFOLD_COPY)
    steps = steps_of_job(doc, job)
    acting = step_by_name(
        steps, "draft-only" if job == "validate" else "Abandon the release"
    )
    assert (
        acting["env"]["TAG_PREFIX"]
        == "${{ needs.resolve-toolchain.outputs.tag-prefix }}"
    )
    run = str(acting["run"])
    assert 'TAG="${TAG_PREFIX}${VERSION}"' in run
    assert "git/refs/tags/${VERSION}" not in run
    if job == "abandon":
        # Branch refs stay bare: release/X.Y.Z never carries the prefix.
        assert "git/refs/heads/release/${VERSION}" in run


def test_scaffold_copy_carries_no_devkit_issue_refs_in_comments_to_prs() -> None:
    """The audit comment must not reference devkit issue numbers.

    ``#NNNN`` in a PR comment autolinks to the *consumer's* issue NNNN, which
    is unrelated — the scaffold copy drops the bare reference.
    """
    doc = load_workflow(SCAFFOLD_COPY)
    abandon_run = run_text_of_job(jobs(doc)["abandon"])
    assert "(#1504)" not in abandon_run
