"""Workflow-shape tests: DEVKIT_TAG_PREFIX threading in the scaffold release set.

Issue #1044: an Action-publishing consumer declares ``DEVKIT_TAG_PREFIX`` in
``.vig-os``; ``resolve-toolchain`` reads it and emits a ``tag-prefix`` output,
which ``release.yml`` threads into the reusable ``release-core.yml`` /
``release-publish.yml`` children as a ``tag_prefix`` ``workflow_call`` input.

These assertions pin the wiring (the composition itself lives in bash ``run:``
blocks, covered by prepare_changelog unit tests and not shape-testable here).

Refs: #1044
"""

from __future__ import annotations

from pathlib import Path

import yaml

# Repository root (tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = REPO_ROOT / "assets" / "workspace"
WORKFLOWS = WORKSPACE / ".github" / "workflows"


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_vig_os_declares_tag_prefix_key() -> None:
    """The scaffold manifest ships the opt-in key (default empty)."""
    text = (WORKSPACE / ".vig-os").read_text(encoding="utf-8")
    assert "DEVKIT_TAG_PREFIX=" in text


def test_resolve_toolchain_emits_tag_prefix_output() -> None:
    """resolve-toolchain declares a tag-prefix output for callers to consume."""
    action = _load(WORKFLOWS.parent / "actions" / "resolve-toolchain" / "action.yml")
    assert "tag-prefix" in action["outputs"]


def test_release_orchestrator_threads_tag_prefix() -> None:
    """release.yml passes tag_prefix into the tag-emitting children."""
    workflow = _load(WORKFLOWS / "release.yml")
    resolve_out = workflow["jobs"]["resolve-toolchain"]["outputs"]
    assert "tag-prefix" in resolve_out
    for job in ("core", "publish"):
        assert "tag_prefix" in workflow["jobs"][job]["with"]


def test_reusable_children_declare_tag_prefix_input() -> None:
    """release-core.yml and release-publish.yml accept the tag_prefix input."""
    for name in ("release-core.yml", "release-publish.yml"):
        workflow = _load(WORKFLOWS / name)
        # PyYAML parses the bare ``on`` key as the boolean True.
        call_inputs = workflow[True]["workflow_call"]["inputs"]
        assert "tag_prefix" in call_inputs
