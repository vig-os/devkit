"""Workflow-shape tests: the scaffold ``promote-release.yml``.

Two pinned features share this file (merged from the former
``test_floating_tags.py`` / ``test_promote_mergeability.py``):

Issue #1045: an opt-in ``.vig-os`` key (comma-separated subset of
``major,minor``) makes the scaffolded ``promote-release.yml`` force-move
floating ``<prefix>X`` / ``<prefix>X.Y`` tags to the promoted release commit —
but only after the Release is published and the release PR is merged (the
post-acceptance gate). The key/output declarations live in
``test_vig_os_manifest.py``; the wiring and the tag-move script shape are
pinned here.

Issue #1132: the ``validate`` job verified the release PR existed, was
non-draft, approved, and CI-green — but never checked whether the PR was
actually *mergeable*. Because the sequence is ``validate → promote (undraft,
irreversible) → merge``, a PR that was BEHIND ``main`` passed validation, the
Release was undrafted, and only then did the merge fail — leaving a
half-promoted release. The validate job must query mergeability and reject a
non-mergeable PR before the promote job undrafts the Release.

Issue #1487: the same gate, the same reasoning — but the *upstream* copy had
it only in ``merge``. Devkit's own ``promote-release.yml`` checked the release
PR's draft status, approvals, CI and (not at all) mergeability after ``promote``
had already moved GHCR ``:latest`` and published the Release, so an unapproved
PR failed the promote from a published state. #1474 made the trigger condition
the default: a final ``release.yml`` run always pushes to the release branch and
so always dismisses the approval. Both copies now carry the gate in ``validate``
*and* keep it in ``merge`` — state can change between the two jobs — so these
suites are parametrized over both copies rather than pinning the scaffold alone.

The tag-move and re-query choreography is bash and not unit-testable here.

Refs: #1045, #1132, #1487
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.workflow_scaffold import (
    REPO_ROOT,
    WORKFLOWS,
    load_workflow,
    step_by_name,
    steps_of_job,
)

if TYPE_CHECKING:
    from pathlib import Path

PROMOTE = WORKFLOWS / "promote-release.yml"

# copy id -> the promote-release.yml carrying the release-PR gate (#1487)
PROMOTE_COPIES: dict[str, Path] = {
    "devkit": REPO_ROOT / ".github" / "workflows" / "promote-release.yml",
    "scaffold": WORKFLOWS / "promote-release.yml",
}
COPIES = list(PROMOTE_COPIES)


# ── floating tags (#1045) ─────────────────────────────────────────────────────


def test_promote_resolve_job_exposes_floating_tags() -> None:
    """promote-release's resolve-toolchain job re-exposes the floating-tags output."""
    workflow = load_workflow(PROMOTE)
    resolve_out = workflow["jobs"]["resolve-toolchain"]["outputs"]
    assert "floating-tags" in resolve_out


def test_promote_has_floating_tags_job_gated_after_merge() -> None:
    """A dedicated move job runs only after merge success and when the opt-in is set."""
    workflow = load_workflow(PROMOTE)
    jobs = workflow["jobs"]
    assert "floating-tags" in jobs
    job = jobs["floating-tags"]
    # Runs after the acceptance gate: Release published (promote) + PR merged.
    assert "merge" in job["needs"]
    guard = job["if"]
    assert "needs.merge.result == 'success'" in guard
    assert "floating-tags" in guard  # off unless DEVKIT_FLOATING_TAGS is set


def test_floating_tags_job_threads_prefix_and_version() -> None:
    """The move step consumes the tag prefix, floating levels, and the version."""
    workflow = load_workflow(PROMOTE)
    steps = workflow["jobs"]["floating-tags"]["steps"]
    move = next(s for s in steps if "floating" in str(s.get("name", "")).lower())
    env = move["env"]
    assert "TAG_PREFIX" in env
    assert "FLOATING_TAGS" in env
    assert "VERSION" in env


def _move_step_script() -> str:
    """The bash body of the ``Move floating major/minor tags`` step."""
    workflow = load_workflow(PROMOTE)
    steps = workflow["jobs"]["floating-tags"]["steps"]
    move = next(s for s in steps if "floating" in str(s.get("name", "")).lower())
    return move["run"]


def _floating_tags_job() -> dict:
    return load_workflow(PROMOTE)["jobs"]["floating-tags"]


def test_move_tag_force_pushes_as_the_release_app() -> None:
    """Floating tags are mutated via ``git push --force`` as the Release App.

    #1377: ``POST /git/refs`` does not honor the Release App's Integration
    ruleset bypass for the ``creation`` rule (first release of every new
    floating level fails HTTP 422), while the very same installation token
    creating tags via ``git push`` is bypassed fine.

    #1508: plumbing that token into the push URL does not deliver it. Checkout
    persists its own credentials as ``http.<host>.extraheader``, and that header
    outranks URL userinfo — so the push authenticated as the Actions identity,
    which this job denies (``contents: read``) and the ruleset does not bypass.
    The token has to reach git through the CHECKOUT.
    """
    job = _floating_tags_job()
    steps = job["steps"]
    token = next(i for i, s in enumerate(steps) if s.get("id") == "release_app_token")
    checkout = next(
        i for i, s in enumerate(steps) if "checkout" in str(s.get("uses", ""))
    )

    assert token < checkout, (
        "the App token must be generated BEFORE checkout, so checkout can "
        "persist it as the credentials git actually uses (#1508)"
    )
    assert steps[checkout].get("with", {}).get("token") == (
        "${{ steps.release_app_token.outputs.token }}"
    ), "checkout must carry the Release App token, not the default github.token"

    script = _move_step_script()
    assert "git push" in script
    assert "--force" in script
    assert "git push --force origin" in script, (
        "push to the remote checkout authenticated; a URL with embedded "
        "userinfo is silently ignored in favour of the extraheader (#1508)"
    )


def test_floating_tags_job_embeds_no_token_in_a_url() -> None:
    """No git remote in the job may carry userinfo — it would be ignored (#1508)."""
    steps = _floating_tags_job()["steps"]
    body = "\n".join(str(s.get("run", "")) for s in steps)

    assert "x-access-token" not in body, (
        "a token in the push/fetch URL is dead weight: checkout's extraheader "
        "wins, so the operation runs under the WRONG identity (#1508)"
    )
    assert "REMOTE_URL" not in body


def test_floating_tags_job_keeps_the_actions_token_read_only() -> None:
    """The fix is the App identity, never a wider GITHUB_TOKEN (#1508)."""
    perms = _floating_tags_job()["permissions"]

    assert perms["contents"] == "read", (
        "granting contents: write would make the push succeed under the "
        "ACTIONS identity, defeating the App-identity model (#1508)"
    )


def test_release_tag_is_fetched_from_the_authenticated_remote() -> None:
    """The shallow tag fetch rides the same credentials as the push (#1508).

    Not cosmetic: on a private consumer an unauthenticated fetch fails outright,
    so the remote must be the one checkout configured.
    """
    script = _move_step_script()
    assert "git fetch --no-tags --depth 1 origin" in script


def test_move_tag_never_mutates_refs_via_rest() -> None:
    """No REST ref mutation remains — the branch-free push path replaced both
    the ``PATCH /git/refs/tags`` move and the ``POST /git/refs`` create (#1377)."""
    script = _move_step_script()
    assert "-X PATCH" not in script  # no REST tag move
    assert "-f ref=" not in script  # no REST tag create


def test_move_tag_idempotence_check_retained() -> None:
    """The read-and-skip guard survives the push rewrite (re-run safe)."""
    script = _move_step_script()
    assert "git/ref/tags/${name}" in script  # gh api GET of the current ref
    assert "skipping" in script


def test_push_failure_emits_actionable_error() -> None:
    """A denied or failed tag push must still fail loud with remediation.

    #1157/#1158 introduced the ``::error`` annotation + the documented
    remediation pointer; #1377 keeps both on the push path.
    """
    script = _move_step_script()
    assert "::error" in script  # a GitHub error annotation, not a bare echo
    # Names the ruleset root cause and the documented remediation.
    assert "ruleset" in script.lower()
    assert "first-release-floating-tags" in script


# ── validate gates on the release PR (#1132, #1487) ───────────────────────────


def _pr_gate_run(copy: str, job: str) -> str:
    """The bash body of the ``Find and verify release PR`` step of ``job``."""
    workflow = load_workflow(PROMOTE_COPIES[copy])
    step = step_by_name(steps_of_job(workflow, job), "Find and verify release PR")
    return step["run"]


def _validate_pr_step_run(copy: str = "scaffold") -> str:
    return _pr_gate_run(copy, "validate")


@pytest.mark.parametrize("copy", COPIES)
def test_validate_gates_release_pr_before_promote(copy: str) -> None:
    """Draft, approval and CI are all checked in validate — before the publish.

    #1487: the upstream copy gated only in ``merge``, which runs *after*
    ``promote`` moved ``:latest`` and undrafted the Release.
    """
    run = _validate_pr_step_run(copy)
    assert "isDraft" in run
    assert "still in draft" in run
    assert "reviewDecision" in run
    assert "not approved" in run
    assert "statusCheckRollup" in run
    assert "failed CI checks" in run


@pytest.mark.parametrize("copy", COPIES)
def test_merge_retains_release_pr_gate(copy: str) -> None:
    """The merge copy of the gate stays: PR state can change between the jobs."""
    run = _pr_gate_run(copy, "merge")
    assert "isDraft" in run
    assert "reviewDecision" in run


@pytest.mark.parametrize("copy", COPIES)
def test_validate_queries_pr_mergeability(copy: str) -> None:
    """The validate PR check fetches the PR's merge state."""
    run = _validate_pr_step_run(copy)
    assert "mergeStateStatus" in run
    assert "mergeable" in run


@pytest.mark.parametrize("copy", COPIES)
def test_validate_rejects_behind_pr(copy: str) -> None:
    """A BEHIND (not-up-to-date) PR is rejected before the irreversible promote."""
    run = _validate_pr_step_run(copy)
    assert "BEHIND" in run


@pytest.mark.parametrize("copy", COPIES)
def test_validate_requeries_unknown_mergeability(copy: str) -> None:
    """GitHub computes mergeability async, so UNKNOWN is re-queried, not trusted."""
    run = _validate_pr_step_run(copy)
    assert "UNKNOWN" in run


# ── protection-aware approval gate (#1506) ────────────────────────────────────
#
# The scaffold copy runs on repos whose Main protection may require 0 approving
# reviews (the smoke repo since org-config#167, and the solo-adoption class).
# There GitHub never computes reviewDecision, so the unconditional gate falls
# into the #438 fallback, counts zero approved reviews, and fails a PR the
# platform itself would merge. The scaffold gates therefore consult the base
# branch's rules first and skip the approval assertion — explicitly, logged —
# when no approving review is required. Draft, CI, and mergeability checks are
# unaffected. Devkit's own copy stays unconditional (#1504 keeps the promote
# gates as they are; devkit's main requires 1 review).


@pytest.mark.parametrize("job", ["validate", "merge"])
def test_scaffold_gate_skips_approval_when_none_required(job: str) -> None:
    """Both scaffold gate copies consult the branch rules and log the skip."""
    run = _pr_gate_run("scaffold", job)
    assert "rules/branches" in run
    assert "required_approving_review_count" in run
    assert "approval gate skipped" in run


@pytest.mark.parametrize("job", ["validate", "merge"])
def test_devkit_gate_stays_unconditional(job: str) -> None:
    """Devkit's own promote gates carry no protection-count skip (#1504)."""
    run = _pr_gate_run("devkit", job)
    assert "rules/branches" not in run
    assert "approval gate skipped" not in run
