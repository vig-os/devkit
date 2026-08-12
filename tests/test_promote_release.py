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

The tag-move and re-query choreography is bash and not unit-testable here.

Refs: #1045, #1132
"""

from __future__ import annotations

from tests.workflow_scaffold import WORKFLOWS, load_workflow

PROMOTE = WORKFLOWS / "promote-release.yml"


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


def test_move_tag_force_pushes_with_explicit_app_token() -> None:
    """Floating tags are mutated via ``git push --force`` with the App token.

    #1377: ``POST /git/refs`` does not honor the Release App's Integration
    ruleset bypass for the ``creation`` rule (first release of every new
    floating level fails HTTP 422), while the very same installation token
    creating tags via ``git push`` is bypassed fine. The token must be plumbed
    explicitly into the push URL — the checkout step's persisted credentials
    are the default ``github.token``, which has no bypass.
    """
    script = _move_step_script()
    assert "git push" in script
    assert "--force" in script
    # Explicit App-token auth, not checkout's persisted credentials.
    assert "x-access-token:${GH_TOKEN}@github.com/${GITHUB_REPOSITORY}" in script


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


# ── validate gates on PR mergeability (#1132) ─────────────────────────────────


def _validate_pr_step_run() -> str:
    workflow = load_workflow(PROMOTE)
    steps = workflow["jobs"]["validate"]["steps"]
    step = next(s for s in steps if s.get("name") == "Find and verify release PR")
    return step["run"]


def test_validate_queries_pr_mergeability() -> None:
    """The validate PR check fetches the PR's merge state."""
    run = _validate_pr_step_run()
    assert "mergeStateStatus" in run
    assert "mergeable" in run


def test_validate_rejects_behind_pr() -> None:
    """A BEHIND (not-up-to-date) PR is rejected before the irreversible promote."""
    run = _validate_pr_step_run()
    assert "BEHIND" in run


def test_validate_requeries_unknown_mergeability() -> None:
    """GitHub computes mergeability async, so UNKNOWN is re-queried, not trusted."""
    run = _validate_pr_step_run()
    assert "UNKNOWN" in run
