"""Workflow-shape + behavior tests: DEVKIT_CI_RUNNER runner override.

Issue #1173: a self-hosted consumer declares ``DEVKIT_CI_RUNNER`` in ``.vig-os``
(comma-separated runner label list); ``resolve-toolchain`` reads it and emits a
``runner-json`` output (a JSON array of labels, defaulting to the hosted runner
when the key is absent), and the scaffolded ``ci.yml`` toolchain jobs consume it
via ``runs-on: ${{ fromJSON(needs.resolve-toolchain.outputs.runner-json) }}``.

The shape assertions pin the wiring; the executed-bash assertions pin the JSON
emission (default, single-label, multi-label) directly against the action's real
``run:`` script.

Refs: #1173
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

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

# The hosted default kept when DEVKIT_CI_RUNNER is absent.
HOSTED_DEFAULT = "ubuntu-24.04"

# The expression the runner-configurable jobs must use for runs-on.
RUNNER_JSON_EXPR = "${{ fromJSON(needs.resolve-toolchain.outputs.runner-json) }}"

# Toolchain jobs that must honor the consumer's runner override.
RUNNER_JSON_JOBS = ("lint", "test", "commit-checks", "summary")


def test_ci_toolchain_jobs_use_runner_json() -> None:
    """lint/test/commit-checks/summary route runs-on through the resolved runner."""
    workflow = _load(WORKFLOWS / "ci.yml")
    for job in RUNNER_JSON_JOBS:
        assert workflow["jobs"][job]["runs-on"] == RUNNER_JSON_EXPR


def test_resolve_toolchain_job_stays_hosted() -> None:
    """The producer job cannot depend on its own output — it stays hosted."""
    workflow = _load(WORKFLOWS / "ci.yml")
    assert workflow["jobs"]["resolve-toolchain"]["runs-on"] == HOSTED_DEFAULT


def test_dependency_review_stays_hosted() -> None:
    """dependency-review is public-repo-only + toolchain-free, so it stays hosted."""
    workflow = _load(WORKFLOWS / "ci.yml")
    assert workflow["jobs"]["dependency-review"]["runs-on"] == HOSTED_DEFAULT


@pytest.mark.parametrize(
    ("runner_value", "expected"),
    [
        pytest.param(None, [HOSTED_DEFAULT], id="key-absent"),
        pytest.param("my-runner", ["my-runner"], id="single-label"),
        pytest.param(
            "self-hosted, linux, x64, meatgrinder",
            ["self-hosted", "linux", "x64", "meatgrinder"],
            id="multi-label-whitespace-trimmed",
        ),
    ],
)
def test_runner_json_emission(
    tmp_path: Path, runner_value: str | None, expected: list[str]
) -> None:
    """DEVKIT_CI_RUNNER => a JSON label array; absent => the hosted default."""
    manifest = "DEVKIT_MODE=direnv\n"
    if runner_value is not None:
        manifest += f"DEVKIT_CI_RUNNER={runner_value}\n"
    outputs = _run_resolve(tmp_path, manifest)
    assert json.loads(outputs["runner-json"]) == expected


def test_runner_json_defaults_when_no_manifest(tmp_path: Path) -> None:
    """No .vig-os at all still yields the hosted default array.

    The default `both` mode then errors on the missing tag (an unrelated
    production error path), but runner-json is emitted before that exit.
    """
    outputs = _run_resolve(tmp_path, None, check=False)
    assert json.loads(outputs["runner-json"]) == [HOSTED_DEFAULT]


@pytest.mark.parametrize("mode", ["direnv", "both"])
def test_runner_json_emitted_in_every_mode(tmp_path: Path, mode: str) -> None:
    """runner-json is emitted regardless of delivery mode."""
    manifest = (
        f"DEVKIT_MODE={mode}\nDEVKIT_VERSION=1.2.3\nDEVKIT_CI_RUNNER=self-hosted\n"
    )
    outputs = _run_resolve(tmp_path, manifest)
    assert json.loads(outputs["runner-json"]) == ["self-hosted"]


# ── Refs policy knob (#1282) ──────────────────────────────────────────────────
# DEVKIT_REFS_POLICY drives CI's validate-commit-range Refs enforcement from the
# same key that steers the validate-commit-msg hook at scaffold time. The
# policy->types mapping lives once in resolve-toolchain (single mapping point for
# the CI surface) and mirrors render_refs_policy in init-workspace.sh. The
# `commit-checks` step consumes the resolved list via env, never inline (the
# env-routing pattern the zizmor gate / #1279 require).

# The full approved-types list `optional` expands to (mirrors the hook `--types`).
FULL_REFS_TYPES = "feat,fix,docs,chore,refactor,perf,test,ci,build,revert,style"

# The step that validates commit messages / PR title in the commit-checks job.
COMMIT_CHECKS_STEP = "Validate commit messages and PR title"


@pytest.mark.parametrize(
    ("policy", "expected"),
    [
        pytest.param(None, "chore", id="key-absent-defaults-chore"),
        pytest.param("chore-optional", "chore", id="chore-optional"),
        pytest.param("optional", FULL_REFS_TYPES, id="optional-full-list"),
        pytest.param("required", "none", id="required-none-sentinel"),
        # The loud guard lives at the write path (init-workspace.sh); by the
        # time CI reads .vig-os the value was validated at scaffold, so a
        # defensive fallback keeps CI from breaking on an unexpected literal.
        pytest.param("garbage", "chore", id="invalid-falls-back-chore"),
    ],
)
def test_refs_optional_types_mapping(
    tmp_path: Path, policy: str | None, expected: str
) -> None:
    """DEVKIT_REFS_POLICY maps to the resolved refs-optional-types list."""
    manifest = "DEVKIT_MODE=direnv\n"
    if policy is not None:
        manifest += f"DEVKIT_REFS_POLICY={policy}\n"
    outputs = _run_resolve(tmp_path, manifest)
    assert outputs["refs-optional-types"] == expected


def _commit_checks_step(workflow: dict) -> dict:
    for step in workflow["jobs"]["commit-checks"]["steps"]:
        if step.get("name") == COMMIT_CHECKS_STEP:
            return step
    raise AssertionError(f"commit-checks step {COMMIT_CHECKS_STEP!r} not found")


def test_resolve_toolchain_job_reexports_refs_optional_types() -> None:
    """ci.yml's resolve-toolchain job maps the action output to a job output.

    `needs.resolve-toolchain.outputs.*` reads JOB outputs, not the composite
    action's — without this mapping the commit-checks env resolves empty and
    the policy silently reverts to the chore default (actionlint catches it).
    """
    workflow = _load(WORKFLOWS / "ci.yml")
    outputs = workflow["jobs"]["resolve-toolchain"]["outputs"]
    assert (
        outputs.get("refs-optional-types")
        == "${{ steps.resolve.outputs.refs-optional-types }}"
    )


def test_commit_checks_step_routes_refs_policy_through_env() -> None:
    """The commit-checks step consumes the resolved list via env, not inline."""
    workflow = _load(WORKFLOWS / "ci.yml")
    step = _commit_checks_step(workflow)
    env_values = step["env"].values()
    assert "${{ needs.resolve-toolchain.outputs.refs-optional-types }}" in env_values


def test_commit_checks_step_passes_refs_optional_types_flag() -> None:
    """The run block forwards the env value to validate-commit-range."""
    workflow = _load(WORKFLOWS / "ci.yml")
    step = _commit_checks_step(workflow)
    assert "--refs-optional-types" in step["run"]
