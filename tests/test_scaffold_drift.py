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

from typing import TYPE_CHECKING

import pytest
import yaml

from tests.workflow_scaffold import (
    WORKFLOWS,
)
from tests.workflow_scaffold import (
    load_workflow as _load,
)
from tests.workflow_scaffold import (
    run_resolve_toolchain as _run_resolve,
)

if TYPE_CHECKING:
    from pathlib import Path

# The scaffold-drift job key in ci.yml.
DRIFT_JOB = "scaffold-drift"


def test_drift_image_is_all_modes_ghcr_ref(tmp_path: Path) -> None:
    """A host-mode (direnv) pin still yields a non-empty devcontainer image ref.

    The `image` output is an explicit empty string for host modes, so the drift
    job — which docker-runs the image on the host — needs a separate ref.
    """
    outputs = _run_resolve(tmp_path, "DEVKIT_MODE=direnv\nDEVKIT_VERSION=1.2.3\n")
    assert outputs["image"] == ""
    assert outputs["drift-image"] == "ghcr.io/vig-os/devcontainer:1.2.3"


@pytest.mark.parametrize(
    ("knob", "expected"),
    [
        pytest.param(None, "true", id="key-absent-defaults-true"),
        pytest.param("true", "true", id="explicit-true"),
        pytest.param("false", "false", id="explicit-false-disables"),
    ],
)
def test_drift_check_resolution(
    tmp_path: Path, knob: str | None, expected: str
) -> None:
    """DEVKIT_DRIFT_CHECK resolves to the gate value; absent => enabled."""
    manifest = "DEVKIT_MODE=direnv\n"
    if knob is not None:
        manifest += f"DEVKIT_DRIFT_CHECK={knob}\n"
    outputs = _run_resolve(tmp_path, manifest)
    assert outputs["drift-check"] == expected


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
