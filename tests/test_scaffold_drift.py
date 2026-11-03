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

import json
import os
import re
import shutil
import subprocess
from typing import TYPE_CHECKING

import pytest
import yaml

from tests.conftest import disable_git_auto_maintenance
from tests.workflow_scaffold import (
    REPO_ROOT,
    WORKFLOWS,
    scaffold_tree,
    step_by_name,
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
        "${{ fromJSON(needs.resolve-toolchain.outputs.runners).small }}"
    )


def test_summary_gates_on_scaffold_drift() -> None:
    """The summary aggregate depends on scaffold-drift and checks its result."""
    workflow = _load(WORKFLOWS / "ci.yml")
    assert DRIFT_JOB in workflow["jobs"]["summary"]["needs"]
    run = workflow["jobs"]["summary"]["steps"][0]["run"]
    assert "needs.scaffold-drift.result" in run


# ── direnv mode: Docker-free drift via nix (#1861) ────────────────────────────

CONTAINER_STEP = "Check for scaffold drift"
NIX_STEP = "Check for scaffold drift (nix)"
CONTAINER_RUNTIMES = re.compile(r"\b(docker|podman)\b")


def _drift_steps() -> list[dict]:
    return _load(WORKFLOWS / "ci.yml")["jobs"][DRIFT_JOB]["steps"]


def test_container_drift_step_is_skipped_in_direnv_mode() -> None:
    """Container/both/bare modes keep the docker path; direnv never reaches it."""
    step = next(x for x in _drift_steps() if x.get("name") == CONTAINER_STEP)
    assert step["if"] == "needs.resolve-toolchain.outputs.mode != 'direnv'"
    assert "docker run" in step["run"]


def test_nix_drift_step_is_direnv_only_and_container_free() -> None:
    """direnv mode runs the pinned scaffold through nix: no docker/podman anywhere."""
    steps = _drift_steps()
    nix_step = next(x for x in steps if x.get("name") == NIX_STEP)
    assert nix_step["if"] == "needs.resolve-toolchain.outputs.mode == 'direnv'"
    assert not CONTAINER_RUNTIMES.search(nix_step["run"])
    assert "nix flake metadata" in nix_step["run"]
    assert "github:vig-os/devkit/${IMAGE_TAG}" in nix_step["run"]
    # the scaffold must not execute via its /bin/bash shebang (absent on NixOS)
    assert 'bash "$scratch/assets/init-workspace.sh"' in nix_step["run"]
    # scratch lives under RUNNER_TEMP and is removed on exit
    assert "RUNNER_TEMP" in nix_step["run"]
    assert "trap " in nix_step["run"]
    # authenticated fetch, token only via step env; tag charset validated
    assert (
        "access-tokens = github.com=${{ github.token }}"
        in nix_step["env"]["NIX_CONFIG"]
    )
    assert "[0-9A-Za-z._-]+" in nix_step["run"]
    assert "NIX_CONFIG" not in nix_step["run"]


def test_direnv_drift_job_provisions_nix_before_the_scaffold() -> None:
    """The shared toolchain preamble (nix) runs first, direnv mode only."""
    steps = _drift_steps()
    names = [str(x.get("name")) for x in steps]
    setup = step_by_name(steps, "Set up devkit toolchain")
    assert setup["if"] == "needs.resolve-toolchain.outputs.mode == 'direnv'"
    assert names.index("Set up devkit toolchain") < names.index(NIX_STEP)


def test_no_container_runtime_outside_the_container_step() -> None:
    """Only the non-direnv container step may name docker/podman in this job."""
    for step in _drift_steps():
        if step.get("name") != CONTAINER_STEP:
            assert not CONTAINER_RUNTIMES.search(step.get("run", "")), step.get("name")


def _gnu_sed() -> bool:
    out = subprocess.run(
        ["sed", "--version"], check=False, capture_output=True, text=True
    )
    return out.returncode == 0 and "GNU" in out.stdout


def _run_nix_drift(
    tmp_path: Path, workspace: Path, tag: str
) -> subprocess.CompletedProcess[str]:
    """Execute the nix drift step's real bash, with `nix` stubbed to this repo."""
    step = step_by_name(_drift_steps(), NIX_STEP)
    stub = tmp_path / "bin"
    stub.mkdir(exist_ok=True)
    nix = stub / "nix"
    nix.write_text(
        f"#!/usr/bin/env bash\nprintf '%s' '{json.dumps({'path': str(REPO_ROOT)})}'\n",
        encoding="utf-8",
    )
    nix.chmod(0o755)
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir(exist_ok=True)
    env = {
        **os.environ,
        "PATH": f"{stub}{os.pathsep}{os.environ['PATH']}",
        "GITHUB_WORKSPACE": str(workspace),
        "RUNNER_TEMP": str(runner_temp),
        "IMAGE_TAG": tag,
        "CONSUMER_REPOSITORY": "test/repo",
    }
    proc = subprocess.run(
        ["bash", "-c", step["run"]],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert list(runner_temp.iterdir()) == [], "scratch dir was not removed"
    return proc


@pytest.mark.skipif(
    not (_gnu_sed() and shutil.which("rsync") and shutil.which("jq")),
    reason="the scaffold needs GNU sed, rsync and jq on PATH (Linux CI / dev shell)",
)
@pytest.mark.parametrize("inox", [False, True])
def test_nix_drift_reports_clean_then_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, inox: bool
) -> None:
    """Parity with the container path: no drift on a fresh scaffold, drift after an edit."""
    tag = "1.2.3"
    monkeypatch.setenv("VIG_OS_VERSION", tag)
    if inox:
        seed = tmp_path / "gitflow"
        seed.mkdir()
        (seed / ".vig-os").write_text(
            "DEVKIT_FEATURES_DISABLED=release,sync-issues,scanning,skills,worktree,gh-templates\n"
            "DEVKIT_REFS_POLICY=optional\n",
            encoding="utf-8",
        )
    ws = scaffold_tree(tmp_path)
    git = [
        "git",
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@t",
        "-c",
        "commit.gpgsign=false",
    ]
    subprocess.run(["git", "init", "-q"], cwd=ws, check=True)
    disable_git_auto_maintenance(ws)
    for key, expected in (("maintenance.auto", "false"), ("gc.auto", "0")):
        config = subprocess.run(
            ["git", "config", "--get", key],
            cwd=ws,
            capture_output=True,
            text=True,
            check=False,
        )
        assert config.stdout.strip() == expected, f"{key} must be {expected}"
    subprocess.run(["git", "add", "-A"], cwd=ws, check=True)
    subprocess.run([*git, "commit", "-qm", "scaffold"], cwd=ws, check=True)

    clean = _run_nix_drift(tmp_path, ws, tag)
    assert clean.returncode == 0, clean.stdout + clean.stderr
    assert "No scaffold drift detected" in clean.stdout

    (ws / "SECURITY.md").write_text("hand edit\n", encoding="utf-8")
    subprocess.run([*git, "commit", "-qam", "edit"], cwd=ws, check=True)
    drift = _run_nix_drift(tmp_path, ws, tag)
    assert drift.returncode == 1, drift.stdout + drift.stderr
    assert "Scaffold drift detected" in drift.stdout + drift.stderr


@pytest.mark.parametrize("renovate", [True, False])
@pytest.mark.parametrize("scanning", [True, False])
@pytest.mark.parametrize(
    ("policy", "exempt", "expected", "types"),
    [
        ("", "", "chore", ""),
        ("required", "", "none", ""),
        ("optional", "", "all", ""),
        ("optional", "", "all", "chore,record"),
        ("required", "record,chore", "all", "chore,record"),
        ("optional", "", "all", "chore"),
        ("required", "docs,test", "docs,test", ""),
    ],
)
def test_managed_docs_follow_manifest(
    tmp_path: Path,
    scanning: bool,
    renovate: bool,
    policy: str,
    exempt: str,
    expected: str,
    types: str,
) -> None:
    """Managed documentation must describe the same settings as the validators."""
    ws = tmp_path / "gitflow"
    ws.mkdir()
    disabled = [
        name
        for name, enabled in [("scanning", scanning), ("renovate", renovate)]
        if not enabled
    ]
    (ws / ".vig-os").write_text(
        f"DEVKIT_FEATURES_DISABLED={','.join(disabled)}\n"
        f"DEVKIT_REFS_POLICY={policy}\nDEVKIT_REFS_OPTIONAL_TYPES={exempt}\n"
        f"DEVKIT_COMMIT_TYPES={types}\n",
        encoding="utf-8",
    )
    scaffold_tree(tmp_path)
    security = (ws / "SECURITY.md").read_text()
    assert ("CodeQL" in security) == scanning
    assert ("Scorecard" in security) == scanning
    assert ("Renovate monitors" in security) == renovate
    assert "Dependency review blocks" in security
    if scanning and renovate:
        template = REPO_ROOT / "assets/workspace/SECURITY.md"
        assert security == template.read_text().replace(
            "{{GITHUB_REPOSITORY}}", "test/repo"
        )
    standard = (ws / "docs/COMMIT_MESSAGE_STANDARD.md").read_text()
    if expected != "chore":
        assert "The Refs line is optional" not in standard
    if expected not in ("chore", "none"):
        assert (
            "Each exempt type also gets an issue-less `<type>/<summary>` branch form"
            in standard
        )
    if expected == "all":
        assert "Optional for all approved types" in standard
        assert "mandatory traceability" not in standard
        assert (
            "At least one reference to a GitHub issue must be present" not in standard
        )
    elif expected == "none":
        assert "Mandatory for all approved types" in standard
        assert "No commit types are exempt" in standard
        assert "Each exempt type also gets" not in standard
        assert "`chore/<summary>` branch form" in standard
        assert "remains allowed under every policy" in standard
        assert "for types where `Refs:` is optional" not in standard
    elif expected == "chore":
        assert "Mandatory for most types" in standard
        assert "**`chore`**" in standard
        template = REPO_ROOT / "assets/workspace/docs/COMMIT_MESSAGE_STANDARD.md"
        assert standard == template.read_text()
    else:
        assert "**`docs`**" in standard and "**`test`**" in standard
        assert "**`chore`**" not in standard
    if "chore" in exempt.split(",") or (policy == "optional" and expected == "all"):
        assert "Maintenance commits" in standard


@pytest.mark.parametrize(
    "anchor",
    ["The following commit types have a relaxed", "Additionally, the CI validator"],
)
def test_commit_standard_rejects_missing_anchor(tmp_path: Path, anchor: str) -> None:
    """A changed template must fail before a splice can corrupt the document."""
    source = (REPO_ROOT / "assets/init-workspace.sh").read_text()
    function = source.split("render_commit_standard() {", 1)[1].split("\n}\n", 1)[0]
    doc = tmp_path / "docs/COMMIT_MESSAGE_STANDARD.md"
    doc.parent.mkdir()
    template = (
        REPO_ROOT / "assets/workspace/docs/COMMIT_MESSAGE_STANDARD.md"
    ).read_text()
    doc.write_text(
        "\n".join(line for line in template.split("\n") if not line.startswith(anchor))
    )
    original = doc.read_text()
    result = subprocess.run(
        [
            "bash",
            "-c",
            'set -e; WORKSPACE_DIR="$1"; RESOLVED_REFS_OPTIONAL_TYPES=none; RESOLVED_COMMIT_TYPES=chore; splice_lines() { echo unexpected-splice; }; render_commit_standard() {'
            + function
            + "\n}; render_commit_standard",
            "test",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "missing or invalid Exemptions anchors" in result.stderr
    assert "unexpected-splice" not in result.stdout
    assert doc.read_text() == original
