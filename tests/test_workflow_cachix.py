"""Workflow-shape tests for the first-class, blocking image-closure Cachix push.

Issue #776 makes the *image* closure push to the ``vig-os`` Cachix cache
first-class and **blocking** on the trusted paths (push to ``dev`` and release),
so published images are guaranteed cache-backed and consumers substitute the
closure instead of rebuilding it from source.

These are pure YAML-shape assertions (no ``nix``/``podman`` needed): they parse
the composite action and the workflows and assert the closure-push step exists,
is *not* ``continue-on-error`` on the trusted paths, and is opt-in (so per-PR CI
stays pull-only).

Refs: #776
"""

from __future__ import annotations

from pathlib import Path

import yaml

# Repository root (tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parent.parent

BUILD_IMAGE_ACTION = REPO_ROOT / ".github" / "actions" / "build-image" / "action.yml"
NIX_IMAGE_WF = REPO_ROOT / ".github" / "workflows" / "nix-image.yml"
RELEASE_WF = REPO_ROOT / ".github" / "workflows" / "release.yml"


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _is_closure_push(step: dict) -> bool:
    """A step that pushes a built store closure to Cachix (the #776 idiom)."""
    run = step.get("run", "")
    return "cachix push" in run and "path-info --recursive" in run


def _steps_of_job(workflow: dict, job: str) -> list[dict]:
    return workflow["jobs"][job]["steps"]


def test_build_image_action_has_opt_in_closure_push() -> None:
    """The build-image composite gained a guarded, blocking closure-push step."""
    action = _load(BUILD_IMAGE_ACTION)

    # Opt-in input keeps per-PR CI pull-only (default false).
    assert "push-image-closure" in action["inputs"], (
        "build-image must expose a push-image-closure input"
    )
    assert action["inputs"]["push-image-closure"]["default"] in ("false", False)

    push_steps = [s for s in action["runs"]["steps"] if _is_closure_push(s)]
    assert len(push_steps) == 1, "expected exactly one closure-push step"
    step = push_steps[0]

    # Blocking: a push failure on a trusted path fails the build.
    assert step.get("continue-on-error") is not True, (
        "the image-closure push must be blocking (no continue-on-error)"
    )

    # Gated on the opt-in flag *and* on the auth token so fork PRs never fail.
    guard = step.get("if", "")
    assert "push-image-closure" in guard
    assert "cachix-auth-token" in guard


def test_nix_image_discovery_push_is_blocking() -> None:
    """The dev discovery workflow pushes the image closure as a blocking step."""
    wf = _load(NIX_IMAGE_WF)
    push_steps = [s for s in _steps_of_job(wf, "build-and-test") if _is_closure_push(s)]
    assert push_steps, "nix-image.yml build-and-test must push the image closure"
    for step in push_steps:
        assert step.get("continue-on-error") is not True, (
            "the discovery image-closure push must be blocking"
        )


def test_release_build_and_test_opts_into_closure_push() -> None:
    """Release build-and-test tells build-image to push (cache-back published images)."""
    wf = _load(RELEASE_WF)
    build_steps = [
        s
        for s in _steps_of_job(wf, "build-and-test")
        if "build-image" in str(s.get("uses", ""))
    ]
    assert build_steps, "release build-and-test must call the build-image action"
    for step in build_steps:
        assert step.get("with", {}).get("push-image-closure") in ("true", True), (
            "release build-and-test must set push-image-closure: 'true'"
        )


def test_release_vulnix_gate_pushes_scan_target_closure() -> None:
    """The release CVE gate pushes the scan-target closure so scans are cache-backed."""
    wf = _load(RELEASE_WF)
    push_steps = [s for s in _steps_of_job(wf, "vulnix-gate") if _is_closure_push(s)]
    assert push_steps, "vulnix-gate must push the devkitImageEnv closure"
    for step in push_steps:
        assert step.get("continue-on-error") is not True, (
            "the scan-target closure push must be blocking"
        )
