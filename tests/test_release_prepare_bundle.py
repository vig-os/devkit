"""Workflow-shape contract: prepare-time bundle rebuild (Refs: #1745).

The release train deadlocked when a consumer with a committed bundle (dist/)
had a stale bundle on dev (from bot PRs like Renovate lockfile bumps that skip
regenerating the artifact). The prepare step opened the release PR, which
immediately triggered `Dist Check` against the stale bundle. The release.yml
candidate's validate gate then aborted before the final-only bundle rebuild
could run.

The fix rebuilds and commits the bundle at PREPARE time, so the artifact is
fresh by the time the release PR triggers `Dist Check`. A shared composite
action extracts the bundle detection and path-listing logic used by both
prepare-release.yml and release-core.yml.
"""

from __future__ import annotations

import pytest

from tests.workflow_scaffold import WORKFLOWS, load_workflow


@pytest.fixture
def prepare_steps() -> list[dict]:
    """Load prepare-release.yml's 'Prepare Release Branch' job steps."""
    workflow = load_workflow(WORKFLOWS / "prepare-release.yml")
    return workflow["jobs"]["prepare"]["steps"]


@pytest.fixture
def finalize_steps() -> list[dict]:
    """Load release-core.yml's finalize job steps."""
    workflow = load_workflow(WORKFLOWS / "release-core.yml")
    return workflow["jobs"]["finalize"]["steps"]


def _step(steps: list[dict], name_fragment: str) -> dict:
    """Find a step by name fragment (case-insensitive)."""
    frag = name_fragment.lower()
    return next(s for s in steps if frag in str(s.get("name", "")).lower())


def _step_index(steps: list[dict], name_fragment: str) -> int:
    """Find step index by name fragment (case-insensitive)."""
    frag = name_fragment.lower()
    for i, step in enumerate(steps):
        if frag in str(step.get("name", "")).lower():
            return i
    raise AssertionError(f"no step matching {name_fragment!r}")


# ─────────────────────────────────────────────────────────────────────────────
# Prepare-time bundle rebuild: detect + build + commit
# ─────────────────────────────────────────────────────────────────────────────


def test_prepare_step_detects_bundle_recipe(prepare_steps: list[dict]) -> None:
    """Prepare job must detect the bundle recipe before the dev commit step."""
    step = _step(prepare_steps, "Detect release bundle")
    assert step is not None, "Prepare job missing bundle detection step"
    assert "just --summary" in str(step.get("run", ""))
    assert "grep -qw bundle" in str(step.get("run", ""))


def test_prepare_detects_bundle_before_dev_commit(
    prepare_steps: list[dict],
) -> None:
    """Bundle detection must precede the dev commit step."""
    detect_idx = _step_index(prepare_steps, "Detect release bundle")
    commit_idx = _step_index(prepare_steps, "Commit prepared CHANGELOG to dev")
    assert detect_idx < commit_idx, (
        "bundle detection must run before committing to dev so the "
        "commit can include the bundle if present"
    )


def test_prepare_builds_bundle_before_dev_commit(
    prepare_steps: list[dict],
) -> None:
    """Bundle build must precede the dev commit step."""
    build_idx = _step_index(prepare_steps, "Build prepare-time artifact")
    commit_idx = _step_index(prepare_steps, "Commit prepared CHANGELOG to dev")
    assert build_idx < commit_idx, (
        "bundle build must run before committing to dev so the "
        "commit can include the bundle if present"
    )


def test_prepare_build_step_runs_when_bundle_detected(
    prepare_steps: list[dict],
) -> None:
    """The build step must be conditional on the detection step's output."""
    build_step = _step(prepare_steps, "Build prepare-time artifact")
    if_condition = str(build_step.get("if", ""))
    assert "steps.bundle.outputs.has_bundle == 'true'" in if_condition or (
        "steps.detect" in if_condition and "has_bundle" in if_condition
    ), "build step must gate on the detection step's has_bundle output"


def test_prepare_build_computes_dist_paths(prepare_steps: list[dict]) -> None:
    """Build step must compute non-ignored dist paths using git ls-files."""
    build_step = _step(prepare_steps, "Build prepare-time artifact")
    run = str(build_step.get("run", ""))
    assert "git ls-files -co --exclude-standard -- dist" in run
    assert "dist_paths=" in run
    assert '>> "$GITHUB_OUTPUT"' in run


def test_prepare_commit_includes_bundle_in_file_paths(
    prepare_steps: list[dict],
) -> None:
    """The dev commit's FILE_PATHS must include the computed dist_paths."""
    commit_step = _step(prepare_steps, "Commit prepared CHANGELOG to dev")
    file_paths = str(commit_step.get("env", {}).get("FILE_PATHS", ""))
    assert "dist_paths" in file_paths, (
        "FILE_PATHS must thread the bundle's computed dist_paths output"
    )
    assert "CHANGELOG.md" in file_paths, "CHANGELOG.md must still be committed"


def test_prepare_detect_step_has_output_id(prepare_steps: list[dict]) -> None:
    """The detect step must expose its has_bundle output."""
    step = _step(prepare_steps, "Detect release bundle")
    assert step.get("id") is not None, (
        "detection step must have an id so its outputs can be referenced"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Shared build logic: prepare-release and release-core use the same action
# ─────────────────────────────────────────────────────────────────────────────


def test_shared_build_action_exists() -> None:
    """A composite action must exist to extract shared bundle build logic."""
    action_path = WORKFLOWS.parent / "actions" / "build-bundle" / "action.yml"
    assert action_path.exists(), (
        f"Shared bundle action not found at {action_path}; "
        "DRY rule requires one copy, not two"
    )


def test_prepare_uses_shared_build_action(prepare_steps: list[dict]) -> None:
    """Prepare-time build must use the shared composite action."""
    build_step = _step(prepare_steps, "Build prepare-time artifact")
    uses = str(build_step.get("uses", ""))
    assert "build-bundle" in uses, (
        "build step must delegate to the shared build-bundle action, not inline the logic"
    )


def test_finalize_uses_shared_build_action(finalize_steps: list[dict]) -> None:
    """Release-core finalize must also use the shared composite action."""
    build_step = _step(finalize_steps, "Build release artifact")
    uses = str(build_step.get("uses", ""))
    assert "build-bundle" in uses, (
        "build step must delegate to the shared build-bundle action, not inline the logic"
    )


def test_prepare_and_finalize_no_duplicate_git_ls_files_logic() -> None:
    """The git ls-files -co logic must appear only once (in the shared action)."""
    prepare_workflow = load_workflow(WORKFLOWS / "prepare-release.yml")
    finalize_workflow = load_workflow(WORKFLOWS / "release-core.yml")

    prepare_text = str(prepare_workflow)
    finalize_text = str(finalize_workflow)

    # Both workflows should reference the shared action, not inline the git ls-files
    pattern = "git ls-files -co --exclude-standard -- dist"

    prepare_count = prepare_text.count(pattern)
    finalize_count = finalize_text.count(pattern)

    # The action definition itself (action.yml) carries one copy; each workflow
    # that loads the action must NOT duplicate it. Zero in prepare (uses action),
    # zero in finalize (uses action, idempotent re-run).
    assert prepare_count == 0, (
        f"prepare-release.yml must not inline git ls-files logic; found {prepare_count} occurrence(s)"
    )
    assert finalize_count == 0, (
        f"release-core.yml must not inline git ls-files logic; found {finalize_count} occurrence(s)"
    )
