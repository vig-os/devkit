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
    REPO_ROOT,
    WORKFLOWS,
)
from tests.workflow_scaffold import (
    exec_resolve_toolchain as _exec_resolve,
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
HOSTED_DEFAULT = "ubuntu-26.04"

# The expression the runner-configurable jobs must use for runs-on.
RUNNER_JSON_EXPR = "${{ fromJSON(needs.resolve-toolchain.outputs.runner-json) }}"

# Toolchain jobs that must honor the consumer's runner override.
RUNNER_JSON_JOBS = (
    "lint",
    "test",
    "commit-checks",
    "scaffold-drift",
    "devkit-staleness",
    "summary",
)


def test_ci_toolchain_jobs_use_runner_json() -> None:
    """lint/test/commit-checks/summary route runs-on through the resolved runner."""
    workflow = _load(WORKFLOWS / "ci.yml")
    for job in RUNNER_JSON_JOBS:
        assert (
            workflow["jobs"][job]["runs-on"]
            == "${{ fromJSON(needs.resolve-toolchain.outputs.runners)."
            + (job if job in ("lint", "test") else "small")
            + " }}"
        )


def test_dependency_review_stays_hosted() -> None:
    """dependency-review is public-repo-only + toolchain-free, so it stays hosted."""
    workflow = _load(WORKFLOWS / "ci.yml")
    assert workflow["jobs"]["dependency-review"]["runs-on"] == HOSTED_DEFAULT


# ── sync-issues.yml's sync job (#1795) ────────────────────────────────────────
# The daily-cron sync job did its real work on the hosted default regardless of
# DEVKIT_CI_RUNNER, unlike ci.yml's toolchain jobs. resolve-toolchain now
# re-exports runner-json here too, and sync routes runs-on through it, exactly
# like ci.yml's toolchain jobs. Its own resolve-toolchain job is not routed through
# runner-json, same chicken-and-egg reasoning as ci.yml's (#1173); see #1796 below.


def test_sync_issues_resolve_toolchain_reexports_runner_json() -> None:
    """sync-issues.yml's resolve-toolchain job maps the action output to a job output."""
    workflow = _load(WORKFLOWS / "sync-issues.yml")
    outputs = workflow["jobs"]["resolve-toolchain"]["outputs"]
    assert outputs.get("runner-json") == "${{ steps.resolve.outputs.runner-json }}"


def test_sync_job_uses_runner_json() -> None:
    """The sync job routes runs-on through the resolved runner, like ci.yml's lanes."""
    workflow = _load(WORKFLOWS / "sync-issues.yml")
    assert workflow["jobs"]["sync"]["runs-on"] == RUNNER_JSON_EXPR


def test_sync_job_needs_resolve_toolchain() -> None:
    """The sync job must depend on resolve-toolchain to read its runner-json output."""
    workflow = _load(WORKFLOWS / "sync-issues.yml")
    needs = workflow["jobs"]["sync"]["needs"]
    needs = [needs] if isinstance(needs, str) else list(needs)
    assert "resolve-toolchain" in needs


# ── resolve-toolchain's own runner (#1796) ────────────────────────────────────
# The producer job cannot read its own runner-json (chicken-and-egg), but `vars`
# resolves server-side before any runner is provisioned, so a repo/org variable
# selects it with no circularity. Default unchanged => no-op until opted in.

RESOLVE_RUNNER_EXPR = "${{ vars.DEVKIT_CI_RESOLVE_RUNNER || 'ubuntu-26.04' }}"

# Every managed workflow that declares a resolve-toolchain job (#1796 table).
RESOLVE_TOOLCHAIN_WORKFLOWS = (
    "ci.yml",
    "sync-issues.yml",
    "sync-main-to-dev.yml",
    "abandon-release.yml",
    "prepare-hotfix.yml",
    "promote-release.yml",
    "release.yml",
)


def test_resolve_toolchain_workflow_list_is_complete() -> None:
    """The pinned list covers every scaffolded workflow declaring the job."""
    declaring = {
        path.name
        for path in WORKFLOWS.glob("*.yml")
        if "resolve-toolchain" in (_load(path).get("jobs") or {})
    }
    assert declaring == set(RESOLVE_TOOLCHAIN_WORKFLOWS)


@pytest.mark.parametrize("workflow_name", RESOLVE_TOOLCHAIN_WORKFLOWS)
def test_resolve_toolchain_runner_is_var_overridable(workflow_name: str) -> None:
    """resolve-toolchain takes its runner from a repo/org variable, hosted default."""
    workflow = _load(WORKFLOWS / workflow_name)
    assert workflow["jobs"]["resolve-toolchain"]["runs-on"] == (
        SAFE_RESOLVE_EXPR if workflow_name == "ci.yml" else RESOLVE_RUNNER_EXPR
    )


@pytest.mark.parametrize("workflow_name", RESOLVE_TOOLCHAIN_WORKFLOWS)
def test_resolve_toolchain_sparse_checkout_has_own_path(workflow_name: str) -> None:
    """The sparse clone lives in its own path, never the shared workspace root (#1860).

    On a persistent self-hosted runner later jobs reuse ``_work/<repo>/<repo>``;
    a sparse clone at the root leaves it unmaterialized for them.
    """
    job = _load(WORKFLOWS / workflow_name)["jobs"]["resolve-toolchain"]
    checkout = next(
        s for s in job["steps"] if str(s.get("uses", "")).startswith("actions/checkout")
    )
    resolve = next(s for s in job["steps"] if s.get("id") == "resolve")
    path = checkout["with"]["path"]
    assert path == ".devkit-resolve"
    assert resolve["uses"] == f"./{path}/.github/actions/resolve-toolchain"
    assert resolve["with"]["working-directory"] == path


@pytest.mark.parametrize(
    ("runner_value", "expected"),
    [
        pytest.param(None, [HOSTED_DEFAULT], id="key-absent"),
        pytest.param("my-runner", ["my-runner"], id="single-label"),
        pytest.param(
            "self-hosted, linux, x64, pool",
            ["self-hosted", "linux", "x64", "pool"],
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


# ── Refs-optional types knob (#1633) ──────────────────────────────────────────
# DEVKIT_REFS_OPTIONAL_TYPES names the exempt set directly, generalizing the
# three-value DEVKIT_REFS_POLICY enum (whose "some types exempt" case is the
# literal `chore`). The narrower key WINS over the policy. Resolution mirrors
# the scaffold render in init-workspace.sh and mkProjectShell — one key, three
# renderers. Guard philosophy matches commit-types/branch-types: the loud guard
# lives at the write path, CI falls back (never weakens) on a bad value.


@pytest.mark.parametrize(
    ("manifest_extra", "expected"),
    [
        pytest.param(
            "DEVKIT_REFS_OPTIONAL_TYPES=chore\n", "chore", id="explicit-default"
        ),
        pytest.param(
            "DEVKIT_COMMIT_TYPES=feat,fix,chore,record\n"
            "DEVKIT_REFS_OPTIONAL_TYPES=chore,record\n",
            "chore,record",
            id="custom-subset",
        ),
        pytest.param(
            "DEVKIT_COMMIT_TYPES=feat,fix,chore,record\n"
            "DEVKIT_REFS_OPTIONAL_TYPES= chore , record \n",
            "chore,record",
            id="whitespace-trimmed",
        ),
        pytest.param(
            "DEVKIT_REFS_OPTIONAL_TYPES= ,\n", "chore", id="all-blank-falls-back"
        ),
        # Fail-safe, mirroring commit-types: a bad value must never break — or
        # weaken — the gate, so CI falls back to the policy mapping.
        pytest.param(
            "DEVKIT_REFS_OPTIONAL_TYPES=chore,Bad-Type\n",
            "chore",
            id="charset-falls-back",
        ),
        # `record` is not an approved commit type here, so the subset rule
        # rejects the list and CI falls back.
        pytest.param(
            "DEVKIT_REFS_OPTIONAL_TYPES=chore,record\n",
            "chore",
            id="non-subset-falls-back",
        ),
    ],
)
def test_refs_optional_types_key_mapping(
    tmp_path: Path, manifest_extra: str, expected: str
) -> None:
    """DEVKIT_REFS_OPTIONAL_TYPES resolves to the refs-optional-types output."""
    outputs = _run_resolve(tmp_path, "DEVKIT_MODE=direnv\n" + manifest_extra)
    assert outputs["refs-optional-types"] == expected


@pytest.mark.parametrize("policy", ["optional", "required", "chore-optional"])
def test_refs_optional_types_key_beats_the_policy_enum(
    tmp_path: Path, policy: str
) -> None:
    """The narrower key wins over DEVKIT_REFS_POLICY, whatever the policy says."""
    manifest = (
        "DEVKIT_MODE=direnv\n"
        "DEVKIT_COMMIT_TYPES=feat,fix,chore,record\n"
        f"DEVKIT_REFS_POLICY={policy}\n"
        "DEVKIT_REFS_OPTIONAL_TYPES=record\n"
    )
    outputs = _run_resolve(tmp_path, manifest)
    assert outputs["refs-optional-types"] == "record"


def test_refs_policy_still_applies_when_the_list_key_is_absent(
    tmp_path: Path,
) -> None:
    """The enum stays sugar over the list — absent list => today's mapping."""
    outputs = _run_resolve(
        tmp_path, "DEVKIT_MODE=direnv\nDEVKIT_REFS_POLICY=required\n"
    )
    assert outputs["refs-optional-types"] == "none"


@pytest.mark.parametrize("bad_value", ["chore,Bad-Type", "record"])
@pytest.mark.parametrize(
    ("policy", "expected"),
    [
        # `optional` is the trap: falling back to the POLICY mapping would
        # expand the exemption to every type, i.e. switch the Refs gate off
        # because the narrower key had a typo. Fail-safe for an EXEMPTION list
        # means the smallest set, not the stock mapping (unlike #1431, where
        # the stock types are a subset of any sane custom list).
        pytest.param("optional", "chore", id="optional-clamped-to-chore"),
        pytest.param("required", "none", id="required-stays-none"),
        pytest.param("chore-optional", "chore", id="chore-optional"),
        pytest.param(None, "chore", id="no-policy"),
    ],
)
def test_invalid_refs_optional_types_never_widens_the_exemption(
    tmp_path: Path, policy: str | None, expected: str, bad_value: str
) -> None:
    """A rejected DEVKIT_REFS_OPTIONAL_TYPES must never relax the gate (#1633)."""
    manifest = "DEVKIT_MODE=direnv\n"
    if policy is not None:
        manifest += f"DEVKIT_REFS_POLICY={policy}\n"
    manifest += f"DEVKIT_REFS_OPTIONAL_TYPES={bad_value}\n"
    outputs = _run_resolve(tmp_path, manifest)
    assert outputs["refs-optional-types"] == expected


def test_invalid_refs_optional_types_warns_loudly(tmp_path: Path) -> None:
    """The fail-safe fallback is never silent — the write path aborts, CI warns."""
    proc, _ = _exec_resolve(
        tmp_path,
        "DEVKIT_MODE=direnv\nDEVKIT_REFS_OPTIONAL_TYPES=chore,Bad-Type\n",
    )
    assert "::warning::Invalid DEVKIT_REFS_OPTIONAL_TYPES" in proc.stdout


# ── Branch types knob + CI branch-name gate (#1432 / #1430) ───────────────────
# DEVKIT_BRANCH_TYPES replaces the issue-numbered branch-type set that the
# local validate-branch-name guard renders from, and — because the local hook
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


# ── One branch-name rule (#1760) ──────────────────────────────────────────────
# The gate no longer spells the rule as its own bash `ALLOWED` alternation: it
# calls vig-utils' validate-branch-name, the implementation the local hook runs
# too, so the accepted shapes cannot drift between the two again. Devkit's own
# ci.yml (the producer, no .vig-os) calls it with the validator's stock
# defaults, which test_flake_hooks pins to nix/hooks.nix's defaultBranchTypes.
DEVKIT_CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"


@pytest.mark.parametrize(
    "path",
    [
        pytest.param(WORKFLOWS / "ci.yml", id="scaffold"),
        pytest.param(DEVKIT_CI, id="devkit"),
    ],
)
def test_branch_name_step_calls_the_shared_validator(path: Path) -> None:
    run = _branch_name_step(_load(path))["run"]
    assert "uv run validate-branch-name" in run
    assert '--branch="${HEAD_REF}"' in run
    # No second rendering of the rule left behind.
    assert "ALLOWED" not in run
    assert "grep" not in run
    assert "${{" not in run


def test_scaffold_branch_name_step_forwards_both_type_sets() -> None:
    run = _branch_name_step(_load(WORKFLOWS / "ci.yml"))["run"]
    assert '--types="${BRANCH_TYPES}"' in run
    assert '--issueless-types="${ISSUELESS_BRANCH_TYPES}"' in run


def test_devkit_branch_name_step_restates_no_type_list() -> None:
    """Devkit's producer CI uses the validator's stock sets, never a copy."""
    step = _branch_name_step(_load(DEVKIT_CI))
    assert "--types" not in step["run"]
    assert "BRANCH_TYPES" not in step.get("env", {})


def _run_branch_gate(
    head_ref: str, branch_types: str, issueless_types: str = "chore"
) -> int:
    """Execute the gate step's real bash against a head ref; return exit code."""
    workflow = _load(WORKFLOWS / "ci.yml")
    step = _branch_name_step(workflow)
    result = subprocess.run(
        ["bash", "-c", step["run"]],
        env={
            **os.environ,
            "HEAD_REF": head_ref,
            "BRANCH_TYPES": branch_types,
            "ISSUELESS_BRANCH_TYPES": issueless_types,
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


# ── Issue-less branch form per Refs-optional type (#1767) ─────────────────────
# Every commit type whose `Refs:` line is optional also gets an issue-less
# `<type>/<summary>` branch form, generalising the old hardcoded `chore/<slug>`
# clause. The set is DERIVED from the resolved refs-optional-types (never a
# second list that could disagree with it), with `chore` as a floor: the
# sync-main-to-dev and devkit-upgrade bot branches are `chore/<slug>`, so no
# Refs policy may take that clause away — `required` (the `none` sentinel)
# included. The default and `required` therefore resolve to plain `chore`, the
# byte-identical pre-#1767 gate.


@pytest.mark.parametrize(
    ("manifest_extra", "expected"),
    [
        pytest.param("", "chore", id="key-absent-defaults-chore"),
        pytest.param(
            "DEVKIT_REFS_OPTIONAL_TYPES=chore,docs\n", "chore,docs", id="chore-docs"
        ),
        # `chore` is a floor, not a member the consumer must remember to keep.
        pytest.param(
            "DEVKIT_REFS_OPTIONAL_TYPES=docs\n", "chore,docs", id="chore-floor"
        ),
        pytest.param(
            "DEVKIT_REFS_OPTIONAL_TYPES=docs,chore\n",
            "chore,docs",
            id="chore-not-duplicated",
        ),
        # `none` is a sentinel type, never a branch prefix.
        pytest.param("DEVKIT_REFS_POLICY=required\n", "chore", id="required"),
        pytest.param(
            "DEVKIT_REFS_POLICY=optional\n",
            "chore,feat,fix,docs,refactor,perf,test,ci,build,revert,style",
            id="optional-every-type",
        ),
        # A rejected list falls back to the clamped exemption, so the branch
        # rule never widens on a typo either.
        pytest.param(
            "DEVKIT_REFS_OPTIONAL_TYPES=docs,Bad-Type\n",
            "chore",
            id="invalid-falls-back",
        ),
    ],
)
def test_issueless_branch_types_mapping(
    tmp_path: Path, manifest_extra: str, expected: str
) -> None:
    """The issue-less branch set follows the resolved Refs-optional set (#1767)."""
    outputs = _run_resolve(tmp_path, "DEVKIT_MODE=direnv\n" + manifest_extra)
    assert outputs["issueless-branch-types"] == expected


def test_resolve_toolchain_job_reexports_issueless_branch_types() -> None:
    """ci.yml's resolve-toolchain job maps the action output to a job output."""
    workflow = _load(WORKFLOWS / "ci.yml")
    outputs = workflow["jobs"]["resolve-toolchain"]["outputs"]
    assert (
        outputs.get("issueless-branch-types")
        == "${{ steps.resolve.outputs.issueless-branch-types }}"
    )


def test_branch_name_step_reads_issueless_types_through_env() -> None:
    """The gate takes the issue-less set from resolve-toolchain via env."""
    workflow = _load(WORKFLOWS / "ci.yml")
    step = _branch_name_step(workflow)
    assert (
        "${{ needs.resolve-toolchain.outputs.issueless-branch-types }}"
        in step["env"].values()
    )


def test_branch_gate_admits_issueless_form_of_refs_optional_types() -> None:
    """A Refs-optional type gets `<type>/<summary>` next to its issue form."""
    assert _run_branch_gate("docs/vendor-quotation", DEFAULT_BRANCH_TYPES) == 1
    assert (
        _run_branch_gate("docs/vendor-quotation", DEFAULT_BRANCH_TYPES, "chore,docs")
        == 0
    )
    # The issue-numbered form stays available alongside it.
    assert _run_branch_gate("docs/12-x", DEFAULT_BRANCH_TYPES, "chore,docs") == 0


def test_branch_gate_issueless_type_outside_branch_types() -> None:
    """Refs-optional but not a branch type: only the issue-less form, like chore."""
    assert (
        _run_branch_gate("record/datasheet", DEFAULT_BRANCH_TYPES, "chore,record") == 0
    )
    # `record/54-x` is still admitted — `54-x` is itself a valid summary slug,
    # exactly as `chore/54-x` always was.
    assert (
        _run_branch_gate("record/Bad_Slug", DEFAULT_BRANCH_TYPES, "chore,record") == 1
    )


@pytest.mark.parametrize(
    "step_name", ["Check declared languages", "Check flake pin lockstep"]
)
def test_ci_gate_steps_run_in_resolve_checkout(step_name: str) -> None:
    """The marker/flake.nix gates read the sparse clone, not the workspace root (#1860)."""
    job = _load(WORKFLOWS / "ci.yml")["jobs"]["resolve-toolchain"]
    step = next(s for s in job["steps"] if s.get("name") == step_name)
    assert step["working-directory"] == ".devkit-resolve"


# ── release-train routing (#1863) ─────────────────────────────────────────────
# Every release-train job takes its runner from DEVKIT_CI_RUNNER (runner-json)
# or, before a runner-json exists, the resolve variable. Hosted-only by design:
# codeql / scorecard / devkit-upgrade (not release train, no .vig-os access).

_RESOLVER_JSON = "${{ fromJSON(needs.resolve-toolchain.outputs.runner-json) }}"
_VALIDATE_JSON = "${{ fromJSON(needs.validate.outputs.runner-json) }}"
_INPUT_JSON = "${{ fromJSON(inputs.runner-json) }}"

# workflow -> expected routing expression for every job that is not the resolver
RELEASE_TRAIN_ROUTING = {
    "prepare-release.yml": _VALIDATE_JSON,
    "prepare-hotfix.yml": _RESOLVER_JSON,
    "release.yml": _RESOLVER_JSON,
    "promote-release.yml": _RESOLVER_JSON,
    "abandon-release.yml": _RESOLVER_JSON,
    "sync-main-to-dev.yml": _RESOLVER_JSON,
    "release-core.yml": _INPUT_JSON,
    "release-publish.yml": _INPUT_JSON,
}
# Seeded, consumer-owned hooks: callers pass them no new input (see the compat
# guard below), so they take the resolve variable like the standalone publish seam.
SEEDED_HOOKS = (
    "release-extension.yml",
    "prepare-release-extension.yml",
    "publish-release-extension.yml",
)


@pytest.mark.parametrize("workflow_name", sorted(RELEASE_TRAIN_ROUTING))
def test_release_train_jobs_route_via_runner_json(workflow_name: str) -> None:
    """No release-train job hard-codes a hosted label (#1863)."""
    expected = RELEASE_TRAIN_ROUTING[workflow_name]
    jobs = _load(WORKFLOWS / workflow_name)["jobs"]
    for name, job in jobs.items():
        if "uses" in job:  # reusable-workflow call: runner chosen inside
            continue
        runs_on = job["runs-on"]
        if runs_on == RESOLVE_RUNNER_EXPR:
            assert name == "resolve-toolchain" or (
                workflow_name == "prepare-release.yml" and name == "validate"
            )
            continue
        assert runs_on == expected, f"{workflow_name}:{name}"


def test_prepare_release_validate_is_the_resolver() -> None:
    """prepare-release has no resolve-toolchain job; `validate` resolves inline."""
    validate = _load(WORKFLOWS / "prepare-release.yml")["jobs"]["validate"]
    assert validate["runs-on"] == RESOLVE_RUNNER_EXPR
    assert (
        validate["outputs"]["runner-json"] == "${{ steps.resolve.outputs.runner-json }}"
    )


@pytest.mark.parametrize(
    "workflow_name",
    [n for n, e in RELEASE_TRAIN_ROUTING.items() if e == _RESOLVER_JSON],
)
def test_release_train_resolver_exports_runner_json(workflow_name: str) -> None:
    """Jobs read runner-json from needs.resolve-toolchain, so it must export it."""
    jobs = _load(WORKFLOWS / workflow_name)["jobs"]
    outputs = jobs["resolve-toolchain"]["outputs"]
    assert outputs["runner-json"] == "${{ steps.resolve.outputs.runner-json }}"
    for name, job in jobs.items():
        if str(job.get("uses", "")).rsplit("/", 1)[-1] in SEEDED_HOOKS:
            continue  # seeded hooks take no runner-json from the caller
        if name != "resolve-toolchain":
            assert "resolve-toolchain" in _needs(job), f"{workflow_name}:{name}"


def _needs(job: dict) -> list[str]:
    needs = job.get("needs", [])
    return [needs] if isinstance(needs, str) else list(needs)


@pytest.mark.parametrize(
    "workflow_name",
    [n for n, e in RELEASE_TRAIN_ROUTING.items() if e == _INPUT_JSON],
)
def test_reusable_release_workflows_declare_runner_json_input(
    workflow_name: str,
) -> None:
    """Reusable release workflows take an optional runner-json, hosted default."""
    workflow = _load(WORKFLOWS / workflow_name)
    on = workflow.get("on", workflow.get(True))
    spec = on["workflow_call"]["inputs"]["runner-json"]
    assert spec["required"] is False
    assert spec["default"] == '["ubuntu-26.04"]'


@pytest.mark.parametrize(
    ("caller", "job", "source"),
    [
        ("release.yml", "core", "needs.resolve-toolchain.outputs.runner-json"),
        ("release.yml", "publish", "needs.resolve-toolchain.outputs.runner-json"),
    ],
)
def test_release_callers_pass_runner_json(caller: str, job: str, source: str) -> None:
    """Callers hand their resolved runner-json to the managed reusable workflows."""
    spec = _load(WORKFLOWS / caller)["jobs"][job]
    assert spec["with"]["runner-json"] == "${{ " + source + " }}"
    assert source.split(".")[1] in _needs(spec)


# Inputs the seeded hooks declared BEFORE #1863 (the oldest supported template).
# Seeded files are never overwritten on upgrade, so an existing consumer's copy
# declares exactly these; a caller passing anything else fails with "Invalid
# input" for every existing consumer.
OLDEST_SEEDED_INPUTS = {
    "release-extension.yml": {
        "version",
        "finalize_sha",
        "release_date",
        "release_kind",
        "publish_version",
    },
    "prepare-release-extension.yml": {
        "version",
        "release_branch",
        "branch_sha",
        "dry_run",
    },
}


def test_callers_pass_only_inputs_the_oldest_seeded_hook_declares() -> None:
    """Managed callers must stay compatible with preserved seeded hook copies."""
    seen = set()
    for path in WORKFLOWS.glob("*.yml"):
        for name, job in (_load(path).get("jobs") or {}).items():
            hook = str(job.get("uses", "")).rsplit("/", 1)[-1]
            if hook in OLDEST_SEEDED_INPUTS:
                seen.add(hook)
                extra = set(job.get("with") or {}) - OLDEST_SEEDED_INPUTS[hook]
                assert not extra, f"{path.name}:{name} passes {extra} to {hook}"
    assert seen == set(OLDEST_SEEDED_INPUTS)


@pytest.mark.parametrize("hook", SEEDED_HOOKS)
def test_seeded_hooks_use_resolve_variable(hook: str) -> None:
    """Seeded hooks take the resolve variable, not a caller-passed runner-json."""
    jobs = _load(WORKFLOWS / hook)["jobs"]
    assert {j["runs-on"] for j in jobs.values()} == {RESOLVE_RUNNER_EXPR}


FORK_PREDICATE = "github.event.pull_request && (github.event.pull_request.head.repo.fork || github.event.pull_request.head.repo.full_name != github.repository)"
SAFE_RESOLVE_EXPR = (
    "${{ ("
    + FORK_PREDICATE
    + " && 'ubuntu-26.04') || vars.CI_RUNNER_SMALL || vars.DEVKIT_CI_RESOLVE_RUNNER || 'ubuntu-26.04' }}"
)
CLASSES = ("small", "large", "xlarge")
LANES = ("lint", "test", "extension", "release-test")


@pytest.mark.parametrize("size", CLASSES)
@pytest.mark.parametrize("source", ("fork", "variable", "legacy-key", "default"))
def test_runner_class_sources(tmp_path, monkeypatch, size, source):
    repo = {"fork": True, "full_name": "example/fork"}
    _runner_event(monkeypatch, {"head": {"repo": repo}} if source == "fork" else None)
    for cls in CLASSES:
        monkeypatch.setenv(
            "RUNNER_" + cls.upper(),
            "pool-" + cls if source in ("fork", "variable") else "",
        )
    manifest = "DEVKIT_MODE=direnv\n"
    if source != "default":
        manifest += "DEVKIT_CI_RUNNER=self-hosted, linux, ,pool\n"
    outputs = _run_resolve(tmp_path, manifest)
    runners = json.loads(outputs["runners"])
    expected = (
        ["pool-" + size]
        if source == "variable"
        else (
            ["self-hosted", "linux", "pool"]
            if source == "legacy-key"
            else [HOSTED_DEFAULT]
        )
    )
    assert runners[size] == expected
    assert json.loads(outputs["runner-sources"])[size] == source
    assert json.loads(outputs["runner-json"]) == runners["small"]
    assert all(runners[lane] == runners["small"] for lane in LANES)


@pytest.mark.parametrize(
    "repo,foreign",
    [
        (None, True),
        ({"fork": False, "full_name": "example/other"}, True),
        ({"fork": True, "full_name": "example/project"}, True),
        ({"fork": False, "full_name": "example/project"}, False),
    ],
)
def test_runner_fork_predicate(tmp_path, monkeypatch, repo, foreign):
    _runner_event(monkeypatch, {"head": {"repo": repo}})
    outputs = _run_resolve(tmp_path, "DEVKIT_MODE=direnv\nDEVKIT_CI_RUNNER=pool\n")
    assert set(json.loads(outputs["runner-sources"]).values()) == {
        "fork" if foreign else "legacy-key"
    }


@pytest.mark.parametrize("size", CLASSES)
@pytest.mark.parametrize(
    "value",
    ["a,b", '["pool-l"]', " pool", "pool ", "po ol", "pool@x", "-pool", "pool\nother"],
)
def test_runner_variable_rejects_malformed(tmp_path, monkeypatch, size, value):
    monkeypatch.setenv("RUNNER_" + size.upper(), value)
    proc, _ = _exec_resolve(tmp_path, "DEVKIT_MODE=direnv\n")
    assert proc.returncode == 1
    assert "::error::" in proc.stdout
    assert "CI_RUNNER_" + size.upper() in proc.stdout


@pytest.mark.parametrize("size", CLASSES)
@pytest.mark.parametrize("value", ["pool._:/-1", " \t\n"])
def test_runner_variable_label_rule(tmp_path, monkeypatch, size, value):
    monkeypatch.setenv("RUNNER_" + size.upper(), value)
    outputs = _run_resolve(tmp_path, "DEVKIT_MODE=direnv\n")
    runners = json.loads(outputs["runners"])
    assert runners[size] == ([value] if value.strip() else [HOSTED_DEFAULT])
    assert all(runners[other] == [HOSTED_DEFAULT] for other in CLASSES if other != size)


def test_runner_unconfigured_defaults(tmp_path):
    outputs = _run_resolve(tmp_path, "DEVKIT_MODE=direnv\n")
    assert all(v == [HOSTED_DEFAULT] for v in json.loads(outputs["runners"]).values())


@pytest.mark.parametrize("name", ["ci.yml", "ci-extension.yml"])
def test_runner_shape_is_fork_safe(name):
    workflow = _load(WORKFLOWS / name)
    for job in workflow["jobs"].values():
        if "runs-on" not in job:
            continue
        expr = job["runs-on"]
        if "${{" not in expr:
            assert expr == HOSTED_DEFAULT
        elif "fromJSON(" not in expr:
            assert FORK_PREDICATE in expr
        elif "inputs.runner-json" in expr:
            callers = [
                j
                for p in WORKFLOWS.glob("*.yml")
                for j in _load(p).get("jobs", {}).values()
                if str(j.get("uses", "")).endswith("/" + name)
            ]
            assert callers
            assert all(
                j["with"]["runner-json"]
                == "${{ toJSON(fromJSON(needs.resolve-toolchain.outputs.runners).extension) }}"
                for j in callers
            )
        else:
            assert expr.startswith(
                "${{ fromJSON(needs.resolve-toolchain.outputs.runners)."
            )
            assert "resolve-toolchain" in _needs(job)


def test_runner_workflows_forbid_unsupported_triggers():
    for path in WORKFLOWS.glob("*.yml"):
        doc = _load(path)
        triggers = doc.get("on", doc.get(True))
        assert not {"workflow_run", "merge_group"}.intersection(triggers)


def test_ci_runner_inputs_and_outputs():
    job = _load(WORKFLOWS / "ci.yml")["jobs"]["resolve-toolchain"]
    for output in ("runners", "runner-sources"):
        assert job["outputs"][output] == "${{ steps.resolve.outputs." + output + " }}"
    step = next(s for s in job["steps"] if s.get("id") == "resolve")
    for size in CLASSES:
        assert (
            step["with"]["runner-" + size]
            == "${{ vars.CI_RUNNER_" + size.upper() + " }}"
        )
    assert (
        step["with"]["legacy-resolve-runner"] == "${{ vars.DEVKIT_CI_RESOLVE_RUNNER }}"
    )


def _runner_event(monkeypatch, pr, base="example/project"):
    """Render the action's actual context env bindings before executing its Bash."""
    repo = ((pr or {}).get("head") or {}).get("repo") or {}
    values = {
        "toJSON(github.event.pull_request)": json.dumps(pr, ensure_ascii=False),
        "github.event.pull_request != null": str(pr is not None).lower(),
        "github.event.pull_request.head.repo.fork": str(
            repo.get("fork", False)
        ).lower(),
        "github.event.pull_request.head.repo.full_name": repo.get("full_name", ""),
        "github.repository": base,
    }
    action = _load(WORKFLOWS.parent / "actions/resolve-toolchain/action.yml")
    for name, expression in action["runs"]["steps"][0]["env"].items():
        if "github." in expression:
            monkeypatch.setenv(
                name, values[expression.removeprefix("${{ ").removesuffix(" }}")]
            )


def test_runner_large_pr_body(tmp_path, monkeypatch):
    pr = {
        "body": "漢" * 50000,
        "head": {"repo": {"fork": False, "full_name": "example/project"}},
    }
    assert len(pr["body"].encode()) > 128 * 1024
    _runner_event(monkeypatch, pr)
    outputs = _run_resolve(tmp_path, "DEVKIT_MODE=direnv\nDEVKIT_CI_RUNNER=pool\n")
    assert set(json.loads(outputs["runner-sources"]).values()) == {"legacy-key"}


def test_runner_ascii_label_under_utf8_locale(tmp_path, monkeypatch):
    monkeypatch.setenv("LC_ALL", "en_US.UTF-8")
    monkeypatch.setenv("RUNNER_LARGE", "pöol")
    proc, _ = _exec_resolve(tmp_path, "DEVKIT_MODE=direnv\n")
    assert proc.returncode == 1
    assert "::error::Invalid CI_RUNNER_LARGE" in proc.stdout


def test_runner_repository_name_case(tmp_path, monkeypatch):
    _runner_event(
        monkeypatch,
        {"head": {"repo": {"fork": False, "full_name": "org/proj"}}},
        "Org/Proj",
    )
    outputs = _run_resolve(tmp_path, "DEVKIT_MODE=direnv\nDEVKIT_CI_RUNNER=pool\n")
    assert set(json.loads(outputs["runner-sources"]).values()) == {"legacy-key"}


# Diagnostics execute the real Bash. S1b will supply lane overrides; until then
# inject an effective map at its assignment to exercise the diagnostics contract.
def _runner_diagnostics(tmp_path, monkeypatch, manifest="", lane_class="small"):
    import tests.workflow_scaffold as scaffold

    summary = tmp_path / "summary"
    summary.touch()
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    if lane_class != "small":
        action = _load(scaffold.RESOLVE_ACTION)
        step = action["runs"]["steps"][0]
        original = (
            "LANE_SIZES='"
            + json.dumps(dict.fromkeys(LANES, "small"), separators=(",", ":"))
            + "'"
        )
        replacement = original.replace('"test":"small"', f'"test":"{lane_class}"')
        assert original in step["run"]
        step["run"] = step["run"].replace(original, replacement)
        monkeypatch.setattr(scaffold, "load_workflow", lambda _: action)
    proc, outputs = _exec_resolve(tmp_path, "DEVKIT_MODE=direnv\n" + manifest)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout, summary.read_text(), outputs


@pytest.mark.parametrize("configured", [False, True])
def test_runner_diagnostics_legacy_migration(tmp_path, monkeypatch, configured):
    if configured:
        monkeypatch.setenv("RUNNER_SMALL", "configured-pool")
    log, _, _ = _runner_diagnostics(
        tmp_path, monkeypatch, "DEVKIT_CI_RUNNER=private-label\n"
    )
    warning = next(line for line in log.splitlines() if "::warning::" in line)
    for text in (
        "DEVKIT_CI_RUNNER",
        "deprecated",
        "N+2",
        "CI_RUNNER_SMALL",
        "repository",
        "private GitHub Free",
        "delete",
        ".vig-os",
        "MIGRATION.md#run-ci-on-self-hosted-runners",
    ):
        assert text in warning
    assert (
        "overrides" if configured else "gh variable set CI_RUNNER_SMALL --body <label>"
    ) in warning
    assert "private-label" not in log
    assert "configured-pool" not in log
    assert "CI_RUNNER_LARGE" not in warning


def test_runner_diagnostics_legacy_variable(tmp_path, monkeypatch):
    monkeypatch.setenv("LEGACY_RESOLVE_RUNNER", "private-label")
    log, _, _ = _runner_diagnostics(tmp_path, monkeypatch)
    assert (
        "::warning::DEVKIT_CI_RESOLVE_RUNNER is deprecated in favour of CI_RUNNER_SMALL"
        in log
    )
    assert "private-label" not in log


@pytest.mark.parametrize("size", CLASSES)
def test_runner_diagnostics_whitespace(tmp_path, monkeypatch, size):
    monkeypatch.setenv("RUNNER_" + size.upper(), " \t\n")
    log, _, outputs = _runner_diagnostics(tmp_path, monkeypatch)
    assert f"::warning::Whitespace-only CI_RUNNER_{size.upper()}" in log
    assert "treated as unset" in log
    assert json.loads(outputs["runner-sources"])[size] == "default"


@pytest.mark.parametrize("size", ["large", "xlarge"])
@pytest.mark.parametrize("source", ["missing", "variable", "legacy-key", "foreign"])
@pytest.mark.parametrize("small_set", [False, True])
def test_runner_diagnostics_opted_in_class(
    tmp_path, monkeypatch, size, source, small_set
):
    if small_set:
        monkeypatch.setenv("RUNNER_SMALL", "pool-s")
    if source == "variable":
        monkeypatch.setenv("RUNNER_" + size.upper(), "pool-extra")
    if source == "foreign":
        _runner_event(monkeypatch, {"head": {"repo": {"fork": True}}})
    manifest = "DEVKIT_CI_RUNNER=pool-legacy\n" if source == "legacy-key" else ""
    log, _, outputs = _runner_diagnostics(tmp_path, monkeypatch, manifest, size)
    opt_warning = [
        line for line in log.splitlines() if "::warning::" in line and "test" in line
    ]
    assert bool(opt_warning) == (source == "missing")
    partial = [line for line in log.splitlines() if "::notice::Partial" in line]
    assert bool(partial) == (
        source == "missing" and small_set or source == "variable" and not small_set
    )
    if source == "missing":
        assert "CI_RUNNER_" + size.upper() in opt_warning[0]
        assert HOSTED_DEFAULT in opt_warning[0]
        assert json.loads(outputs["runners"])["test"] == [HOSTED_DEFAULT]


@pytest.mark.parametrize("unused_set", [False, True])
def test_runner_diagnostics_default_map_complete(tmp_path, monkeypatch, unused_set):
    monkeypatch.setenv("RUNNER_SMALL", HOSTED_DEFAULT)
    if unused_set:
        monkeypatch.setenv("RUNNER_LARGE", "pool-unused")
    log, summary, outputs = _runner_diagnostics(tmp_path, monkeypatch)
    assert "::notice::" not in log
    assert "::warning::" not in log
    for size, source in json.loads(outputs["runner-sources"]).items():
        assert f"| {size} | {source} |" in summary
    assert "pool-unused" not in summary


@pytest.mark.parametrize("private", [False, True])
@pytest.mark.parametrize("foreign", [False, True])
@pytest.mark.parametrize("configured", [False, True])
def test_runner_diagnostics_private_notice(
    tmp_path, monkeypatch, private, foreign, configured
):
    monkeypatch.setenv("REPOSITORY_PRIVATE", str(private).lower())
    if foreign:
        _runner_event(monkeypatch, {"head": {"repo": {"fork": True}}})
    if configured:
        monkeypatch.setenv("RUNNER_SMALL", HOSTED_DEFAULT)
    log, summary, _ = _runner_diagnostics(tmp_path, monkeypatch)
    expected = private and not foreign and not configured
    assert ("::notice::CI runs on hosted runners" in log) == expected
    assert ("GitHub Free organization variables" in summary) == expected
    if expected:
        assert "repository-level variables" in log
        assert "private repos" in log
