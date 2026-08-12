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
import os
import subprocess
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


# ── Commit types knob (#1431) ─────────────────────────────────────────────────
# DEVKIT_COMMIT_TYPES replaces the approved-commit-types list CI's
# validate-commit-range enforces, from the same key that steers the
# validate-commit-msg hook's `--types` arg at scaffold time. The list->output
# mapping lives once in resolve-toolchain (single mapping point for the CI
# surface) and mirrors render_commit_types in init-workspace.sh; the refs-policy
# `optional` expansion follows the RESOLVED list so the two knobs compose. The
# commit-checks step consumes the list via env, never inline (zizmor / #1279).

# The default approved types emitted when the key is absent (mirrors the hook).
DEFAULT_COMMIT_TYPES = "feat,fix,docs,chore,refactor,perf,test,ci,build,revert,style"


@pytest.mark.parametrize(
    ("types_value", "expected"),
    [
        pytest.param(None, DEFAULT_COMMIT_TYPES, id="key-absent-defaults"),
        pytest.param(
            "feat,fix,chore,record", "feat,fix,chore,record", id="custom-list"
        ),
        pytest.param(
            "feat, fix, chore, record",
            "feat,fix,chore,record",
            id="whitespace-trimmed",
        ),
        # The loud guard lives at the write path (init-workspace.sh); by the
        # time CI reads .vig-os the value was validated at scaffold, so a
        # defensive fallback keeps CI from breaking (or weakening the gate) on
        # an unexpected literal.
        pytest.param("feat,Bad-Type", DEFAULT_COMMIT_TYPES, id="invalid-falls-back"),
        pytest.param(" ,", DEFAULT_COMMIT_TYPES, id="all-blank-falls-back"),
    ],
)
def test_commit_types_mapping(
    tmp_path: Path, types_value: str | None, expected: str
) -> None:
    """DEVKIT_COMMIT_TYPES maps to the resolved commit-types list."""
    manifest = "DEVKIT_MODE=direnv\n"
    if types_value is not None:
        manifest += f"DEVKIT_COMMIT_TYPES={types_value}\n"
    outputs = _run_resolve(tmp_path, manifest)
    assert outputs["commit-types"] == expected


def test_refs_optional_expansion_follows_commit_types(tmp_path: Path) -> None:
    """DEVKIT_REFS_POLICY=optional expands to the RESOLVED commit-types list.

    With a custom DEVKIT_COMMIT_TYPES, `optional` must mirror that list — not
    the hardcoded default — or the hook and CI would disagree about which
    types exist (#1431 composition over the #1282 mapping).
    """
    manifest = (
        "DEVKIT_MODE=direnv\n"
        "DEVKIT_REFS_POLICY=optional\n"
        "DEVKIT_COMMIT_TYPES=feat,fix,record\n"
    )
    outputs = _run_resolve(tmp_path, manifest)
    assert outputs["refs-optional-types"] == "feat,fix,record"


def test_resolve_toolchain_job_reexports_commit_types() -> None:
    """ci.yml's resolve-toolchain job maps the action output to a job output."""
    workflow = _load(WORKFLOWS / "ci.yml")
    outputs = workflow["jobs"]["resolve-toolchain"]["outputs"]
    assert outputs.get("commit-types") == "${{ steps.resolve.outputs.commit-types }}"


def test_commit_checks_step_routes_commit_types_through_env() -> None:
    """The commit-checks step consumes the resolved list via env, not inline."""
    workflow = _load(WORKFLOWS / "ci.yml")
    step = _commit_checks_step(workflow)
    env_values = step["env"].values()
    assert "${{ needs.resolve-toolchain.outputs.commit-types }}" in env_values


def test_commit_checks_step_passes_types_flag() -> None:
    """The run block forwards the env value to validate-commit-range.

    Asserted with the env reference (not a bare `--types` substring, which
    `--refs-optional-types` already contains).
    """
    workflow = _load(WORKFLOWS / "ci.yml")
    step = _commit_checks_step(workflow)
    assert '--types "${COMMIT_TYPES}"' in step["run"]


# ── Branch types knob + CI branch-name gate (#1432 / #1430) ───────────────────
# DEVKIT_BRANCH_TYPES replaces the issue-numbered branch-type set that the
# local no-commit-to-branch guard renders from, and — because the local hook
# depends on local git config that a fresh clone does not have (#1430) — the
# same resolved set drives a CI branch-name gate: a commit-checks step
# validating the PR head ref. The list->output mapping lives once in
# resolve-toolchain and mirrors render_branch_types in init-workspace.sh; the
# step consumes the head ref and the list via env, never inline (zizmor /
# #1279). The CI allowance set is a SUPERSET of the local hook's: automation
# branches (release/X.Y.Z, renovate/*, chore/<slug> bot branches, worktree/<n>)
# never run local hooks but do open PRs.

# The default issue-numbered branch types emitted when the key is absent.
DEFAULT_BRANCH_TYPES = "feature,bugfix,hotfix,release,docs,test,refactor"

# The commit-checks step that validates the PR head ref.
BRANCH_NAME_STEP = "Validate branch name"


@pytest.mark.parametrize(
    ("types_value", "expected"),
    [
        pytest.param(None, DEFAULT_BRANCH_TYPES, id="key-absent-defaults"),
        pytest.param(
            "feature,bugfix,record", "feature,bugfix,record", id="custom-list"
        ),
        pytest.param(
            "feature, bugfix, record",
            "feature,bugfix,record",
            id="whitespace-trimmed",
        ),
        # The loud guard lives at the write path (init-workspace.sh); by the
        # time CI reads .vig-os the value was validated at scaffold, so a
        # defensive fallback keeps CI from breaking (or weakening the gate) on
        # an unexpected literal.
        pytest.param("feature,Bad-Type", DEFAULT_BRANCH_TYPES, id="invalid-falls-back"),
        pytest.param(" ,", DEFAULT_BRANCH_TYPES, id="all-blank-falls-back"),
    ],
)
def test_branch_types_mapping(
    tmp_path: Path, types_value: str | None, expected: str
) -> None:
    """DEVKIT_BRANCH_TYPES maps to the resolved branch-types list."""
    manifest = "DEVKIT_MODE=direnv\n"
    if types_value is not None:
        manifest += f"DEVKIT_BRANCH_TYPES={types_value}\n"
    outputs = _run_resolve(tmp_path, manifest)
    assert outputs["branch-types"] == expected


def test_resolve_toolchain_job_reexports_branch_types() -> None:
    """ci.yml's resolve-toolchain job maps the action output to a job output."""
    workflow = _load(WORKFLOWS / "ci.yml")
    outputs = workflow["jobs"]["resolve-toolchain"]["outputs"]
    assert outputs.get("branch-types") == "${{ steps.resolve.outputs.branch-types }}"


def _branch_name_step(workflow: dict) -> dict:
    for step in workflow["jobs"]["commit-checks"]["steps"]:
        if step.get("name") == BRANCH_NAME_STEP:
            return step
    raise AssertionError(f"commit-checks step {BRANCH_NAME_STEP!r} not found")


def test_branch_name_step_routes_inputs_through_env() -> None:
    """The gate reads the head ref and the resolved types via env, not inline.

    The head ref is attacker-controlled text; inline ``${{ }}`` in the run
    block is the template-injection shape the zizmor gate exists to refuse.
    """
    workflow = _load(WORKFLOWS / "ci.yml")
    step = _branch_name_step(workflow)
    env_values = step["env"].values()
    assert "${{ github.head_ref }}" in env_values
    assert "${{ needs.resolve-toolchain.outputs.branch-types }}" in env_values
    assert "${{" not in step["run"]


def test_branch_name_step_precedes_commit_validation() -> None:
    """The cheap head-ref check fails fast, before the range walk."""
    workflow = _load(WORKFLOWS / "ci.yml")
    names = [step.get("name") for step in workflow["jobs"]["commit-checks"]["steps"]]
    assert names.index(BRANCH_NAME_STEP) < names.index(COMMIT_CHECKS_STEP)


def _run_branch_gate(head_ref: str, branch_types: str) -> int:
    """Execute the gate step's real bash against a head ref; return exit code."""
    workflow = _load(WORKFLOWS / "ci.yml")
    step = _branch_name_step(workflow)
    result = subprocess.run(
        ["bash", "-c", step["run"]],
        env={
            **os.environ,
            "HEAD_REF": head_ref,
            "BRANCH_TYPES": branch_types,
        },
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode


@pytest.mark.parametrize(
    "head_ref",
    [
        # Human topic branches (the local hook's own shapes).
        pytest.param("feature/12-x", id="feature"),
        pytest.param("chore/foo-bar", id="chore-slug"),
        pytest.param("worktree/9", id="worktree"),
        # Long-lived branches: the local hook allows committing on them, so a
        # deliberate PR from one stays possible.
        pytest.param("dev", id="dev"),
        pytest.param("main", id="main"),
        # Automation branches that never run local hooks but do open PRs.
        pytest.param("release/1.7.1", id="release-train"),
        pytest.param("renovate/lock-file-maintenance", id="renovate"),
        pytest.param("renovate/github-actions-(minor-and-patch)", id="renovate-parens"),
        pytest.param("chore/sync-main-to-dev-123-1", id="sync-bot"),
        pytest.param("chore/devkit-1-7-1", id="upgrade-bot"),
    ],
)
def test_branch_gate_allows(head_ref: str) -> None:
    """The default gate admits every conforming and automation head ref."""
    assert _run_branch_gate(head_ref, DEFAULT_BRANCH_TYPES) == 0


@pytest.mark.parametrize(
    "head_ref",
    [
        # The #1430 incident literal: `feat` is a commit type, not a branch type.
        pytest.param("feat/rust-language-pack", id="feat-prefix"),
        pytest.param("random-branch", id="no-convention"),
        pytest.param("record/54-x", id="record-not-in-defaults"),
        pytest.param("release/1.7", id="release-partial-version"),
        pytest.param("renovated/x", id="renovate-prefix-confusion"),
    ],
)
def test_branch_gate_rejects(head_ref: str) -> None:
    """The default gate refuses non-conforming head refs."""
    assert _run_branch_gate(head_ref, DEFAULT_BRANCH_TYPES) == 1


def test_branch_gate_follows_custom_types() -> None:
    """A custom DEVKIT_BRANCH_TYPES steers the gate like the local guard."""
    custom = DEFAULT_BRANCH_TYPES + ",record"
    assert _run_branch_gate("record/54-x", custom) == 0
    assert _run_branch_gate("record/no-issue", custom) == 1
