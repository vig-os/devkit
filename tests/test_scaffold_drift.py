"""Workflow-shape + behavior tests: scaffold-drift CI gate (DEVKIT_DRIFT_CHECK).

Issue #1295: the scaffolded ``ci.yml`` gains a ``scaffold-drift`` job that
re-runs the pinned devkit version's scaffold over the checkout and fails when
any managed file diverges — i.e. ``DEVKIT_VERSION`` was bumped without
re-scaffolding, or a managed file was hand-edited. ``resolve-toolchain`` reads
the opt-out knob ``DEVKIT_DRIFT_CHECK`` from ``.vig-os`` and emits a
``drift-check`` output (default ``true`` when the key is absent); the job
self-skips at runtime when it resolves ``false``.

The mechanism is re-scaffold + ``git diff`` (not ``install.sh --preview``): the
preview report classifies OVERWRITTEN by path existence, not content, so it
cannot distinguish genuine drift from an up-to-date managed file. Re-running
``init-workspace.sh --force`` rewrites the managed files to exactly what the pin
would produce while preserving the preserved set + persisted ``.vig-os`` values
by construction; ``git diff`` then surfaces any divergence.

Refs: #1295
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import yaml

# Repository root (tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = REPO_ROOT / "assets" / "workspace"
WORKFLOWS = WORKSPACE / ".github" / "workflows"
RESOLVE_ACTION = WORKFLOWS.parent / "actions" / "resolve-toolchain" / "action.yml"

# The scaffold-drift job key in ci.yml.
DRIFT_JOB = "scaffold-drift"


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _run_resolve(
    tmp_path: Path, manifest: str | None, *, check: bool = True
) -> dict[str, str]:
    """Execute the resolve-toolchain step's real bash against a .vig-os manifest.

    Returns the parsed GITHUB_OUTPUT key=value map. ``drift-check`` is emitted
    early (before tag resolution), alongside runner-json.
    """
    action = _load(RESOLVE_ACTION)
    script = action["runs"]["steps"][0]["run"]

    if manifest is not None:
        (tmp_path / ".vig-os").write_text(manifest, encoding="utf-8")

    github_output = tmp_path / "github_output"
    github_output.touch()

    env = {
        **os.environ,
        "INPUT_IMAGE_TAG": "",
        "GITHUB_OUTPUT": str(github_output),
    }
    subprocess.run(
        ["bash", "-c", script],
        cwd=tmp_path,
        env=env,
        check=check,
        capture_output=True,
        text=True,
    )

    outputs: dict[str, str] = {}
    for line in github_output.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            outputs[key] = value
    return outputs


# ── Manifest knob ─────────────────────────────────────────────────────────────


def test_vig_os_declares_drift_check_key() -> None:
    """The scaffold manifest ships the opt-out key (default empty => enabled)."""
    text = (WORKSPACE / ".vig-os").read_text(encoding="utf-8")
    assert "DEVKIT_DRIFT_CHECK=" in text


# ── resolve-toolchain output ──────────────────────────────────────────────────


def test_resolve_toolchain_emits_drift_check_output() -> None:
    """resolve-toolchain declares a drift-check output for ci.yml to gate on."""
    action = _load(RESOLVE_ACTION)
    assert "drift-check" in action["outputs"]


def test_resolve_toolchain_emits_drift_image_output() -> None:
    """resolve-toolchain declares an all-modes image ref for the drift job."""
    action = _load(RESOLVE_ACTION)
    assert "drift-image" in action["outputs"]


def test_drift_image_is_all_modes_ghcr_ref(tmp_path: Path) -> None:
    """A host-mode (direnv) pin still yields a non-empty devcontainer image ref.

    The `image` output is an explicit empty string for host modes, so the drift
    job — which docker-runs the image on the host — needs a separate ref.
    """
    outputs = _run_resolve(tmp_path, "DEVKIT_MODE=direnv\nDEVKIT_VERSION=1.2.3\n")
    assert outputs["image"] == ""
    assert outputs["drift-image"] == "ghcr.io/vig-os/devcontainer:1.2.3"


def test_drift_check_defaults_true_when_key_absent(tmp_path: Path) -> None:
    """No DEVKIT_DRIFT_CHECK => the enabled default (`true`)."""
    outputs = _run_resolve(tmp_path, "DEVKIT_MODE=direnv\n")
    assert outputs["drift-check"] == "true"


def test_drift_check_false_maps_to_false(tmp_path: Path) -> None:
    """An explicit `false` disables the gate."""
    outputs = _run_resolve(tmp_path, "DEVKIT_MODE=direnv\nDEVKIT_DRIFT_CHECK=false\n")
    assert outputs["drift-check"] == "false"


def test_drift_check_true_maps_to_true(tmp_path: Path) -> None:
    """An explicit `true` keeps the gate enabled."""
    outputs = _run_resolve(tmp_path, "DEVKIT_MODE=direnv\nDEVKIT_DRIFT_CHECK=true\n")
    assert outputs["drift-check"] == "true"


def test_drift_check_emitted_in_every_mode(tmp_path: Path) -> None:
    """drift-check is emitted regardless of delivery mode."""
    outputs = _run_resolve(
        tmp_path, "DEVKIT_MODE=both\nDEVKIT_VERSION=1.2.3\nDEVKIT_DRIFT_CHECK=false\n"
    )
    assert outputs["drift-check"] == "false"


# ── ci.yml wiring ─────────────────────────────────────────────────────────────


def test_resolve_toolchain_job_reexports_drift_check() -> None:
    """The resolve-toolchain job re-exports drift-check so needs can consume it."""
    workflow = _load(WORKFLOWS / "ci.yml")
    outputs = workflow["jobs"]["resolve-toolchain"]["outputs"]
    assert "drift-check" in outputs


def test_ci_declares_scaffold_drift_job() -> None:
    """ci.yml carries the scaffold-drift job, wired to resolve-toolchain."""
    workflow = _load(WORKFLOWS / "ci.yml")
    assert DRIFT_JOB in workflow["jobs"]
    assert workflow["jobs"][DRIFT_JOB]["needs"] == ["resolve-toolchain"]


def test_scaffold_drift_gated_on_pr_and_knob() -> None:
    """The job runs on PRs only (cost) and self-skips when the knob is false."""
    workflow = _load(WORKFLOWS / "ci.yml")
    gate = workflow["jobs"][DRIFT_JOB]["if"]
    assert "github.event_name == 'pull_request'" in gate
    assert "drift-check" in gate
    assert "'false'" in gate


def test_scaffold_drift_runs_rescaffold_and_diff() -> None:
    """The job re-runs init-workspace.sh and diffs the managed tree for drift."""
    workflow = _load(WORKFLOWS / "ci.yml")
    run_blocks = "\n".join(
        step.get("run", "") for step in workflow["jobs"][DRIFT_JOB]["steps"]
    )
    assert "init-workspace.sh" in run_blocks
    assert "--force" in run_blocks
    assert "git" in run_blocks and "diff" in run_blocks


def test_scaffold_drift_uses_resolved_image_ref() -> None:
    """The job docker-runs the resolved image ref, not a hardcoded ghcr literal.

    The #991 SSoT invariant keeps ghcr.io/vig-os/devcontainer out of ci.yml.
    """
    workflow = _load(WORKFLOWS / "ci.yml")
    job_text = yaml.safe_dump(workflow["jobs"][DRIFT_JOB])
    assert "drift-image" in job_text
    assert "ghcr.io/vig-os/devcontainer" not in job_text


def test_scaffold_drift_honors_runner_override() -> None:
    """The job routes runs-on through the resolved runner (self-hosted aware)."""
    workflow = _load(WORKFLOWS / "ci.yml")
    assert workflow["jobs"][DRIFT_JOB]["runs-on"] == (
        "${{ fromJSON(needs.resolve-toolchain.outputs.runner-json) }}"
    )


def test_summary_gates_on_scaffold_drift() -> None:
    """The summary aggregate depends on scaffold-drift and checks its result."""
    workflow = _load(WORKFLOWS / "ci.yml")
    assert DRIFT_JOB in workflow["jobs"]["summary"]["needs"]
    run = workflow["jobs"]["summary"]["steps"][0]["run"]
    assert "needs.scaffold-drift.result" in run
