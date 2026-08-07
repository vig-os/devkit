"""Workflow-shape tests: DEVKIT_FLOATING_TAGS moved by scaffold promote-release.

Issue #1045: an opt-in ``.vig-os`` key (comma-separated subset of ``major,minor``)
makes the scaffolded ``promote-release.yml`` force-move floating ``<prefix>X`` /
``<prefix>X.Y`` tags to the promoted release commit — but only after the Release
is published and the release PR is merged (the post-acceptance gate).

These assertions pin the wiring: resolve-toolchain emits ``floating-tags``, the
promote workflow threads it, and the move job is gated on merge success and the
opt-in being set. The tag-move choreography itself is bash and not unit-testable
here.

Refs: #1045
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = REPO_ROOT / "assets" / "workspace"
WORKFLOWS = WORKSPACE / ".github" / "workflows"


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_vig_os_declares_floating_tags_key() -> None:
    """The scaffold manifest ships the opt-in key (default empty)."""
    text = (WORKSPACE / ".vig-os").read_text(encoding="utf-8")
    assert "DEVKIT_FLOATING_TAGS=" in text


def test_resolve_toolchain_emits_floating_tags_output() -> None:
    """resolve-toolchain declares a floating-tags output."""
    action = _load(WORKFLOWS.parent / "actions" / "resolve-toolchain" / "action.yml")
    assert "floating-tags" in action["outputs"]


def test_promote_resolve_job_exposes_floating_tags() -> None:
    """promote-release's resolve-toolchain job re-exposes the floating-tags output."""
    workflow = _load(WORKFLOWS / "promote-release.yml")
    resolve_out = workflow["jobs"]["resolve-toolchain"]["outputs"]
    assert "floating-tags" in resolve_out


def test_promote_has_floating_tags_job_gated_after_merge() -> None:
    """A dedicated move job runs only after merge success and when the opt-in is set."""
    workflow = _load(WORKFLOWS / "promote-release.yml")
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
    workflow = _load(WORKFLOWS / "promote-release.yml")
    steps = workflow["jobs"]["floating-tags"]["steps"]
    move = next(s for s in steps if "floating" in str(s.get("name", "")).lower())
    env = move["env"]
    assert "TAG_PREFIX" in env
    assert "FLOATING_TAGS" in env
    assert "VERSION" in env


def _move_step_script() -> str:
    """The bash body of the ``Move floating major/minor tags`` step."""
    workflow = _load(WORKFLOWS / "promote-release.yml")
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
    """No REST ref mutation remains, but the trap is documented in a comment.

    The ``PATCH /git/refs/tags`` move and the ``POST /git/refs`` create are
    both replaced by the single branch-free push path. A comment must still
    name ``POST /git/refs`` and why it is avoided, so the REST trap is not
    reintroduced (#1377).
    """
    script = _move_step_script()
    assert "-X PATCH" not in script  # no REST tag move
    assert "-f ref=" not in script  # no REST tag create
    assert "POST /git/refs" in script  # the why-not comment stays


def test_move_tag_idempotence_check_retained() -> None:
    """The read-and-skip guard survives the push rewrite (re-run safe)."""
    script = _move_step_script()
    assert "git/ref/tags/${name}" in script  # gh api GET of the current ref
    assert "skipping" in script


def test_push_failure_emits_actionable_error() -> None:
    """A denied or failed tag push must still fail loud with remediation.

    #1157/#1158 introduced the ``::error`` annotation + MIGRATION.md fallback;
    #1377 keeps both but drops the moot "grant a creation bypass" remediation —
    the bypass already exists, and the push path honors it.
    """
    script = _move_step_script()
    assert "::error" in script  # a GitHub error annotation, not a bare echo
    # Names the ruleset root cause and the documented remediation.
    assert "ruleset" in script.lower()
    assert "first-release-floating-tags" in script
    # The old remediation is moot: the App already has the bypass.
    assert "grant the Release App a 'creation' bypass" not in script
