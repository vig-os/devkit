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
