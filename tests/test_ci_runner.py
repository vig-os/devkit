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
from pathlib import Path

import pytest
import yaml

# Repository root (tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = REPO_ROOT / "assets" / "workspace"
WORKFLOWS = WORKSPACE / ".github" / "workflows"
RESOLVE_ACTION = WORKFLOWS.parent / "actions" / "resolve-toolchain" / "action.yml"

# The hosted default kept when DEVKIT_CI_RUNNER is absent.
HOSTED_DEFAULT = "ubuntu-24.04"

# The expression the runner-configurable jobs must use for runs-on.
RUNNER_JSON_EXPR = "${{ fromJSON(needs.resolve-toolchain.outputs.runner-json) }}"

# Toolchain jobs that must honor the consumer's runner override.
RUNNER_JSON_JOBS = ("lint", "test", "commit-checks", "summary")


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_vig_os_declares_ci_runner_key() -> None:
    """The scaffold manifest ships the opt-in key (default empty)."""
    text = (WORKSPACE / ".vig-os").read_text(encoding="utf-8")
    assert "DEVKIT_CI_RUNNER=" in text


def test_resolve_toolchain_emits_runner_json_output() -> None:
    """resolve-toolchain declares a runner-json output for callers to consume."""
    action = _load(RESOLVE_ACTION)
    assert "runner-json" in action["outputs"]


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


def _run_resolve(
    tmp_path: Path, manifest: str | None, *, check: bool = True
) -> dict[str, str]:
    """Execute the resolve-toolchain step's real bash against a .vig-os manifest.

    Returns the parsed GITHUB_OUTPUT key=value map. ``runner-json`` is emitted
    early (before mode/tag resolution), so callers exercising an error path
    (e.g. no manifest => default `both` mode with no tag) pass ``check=False``.
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


def test_runner_json_defaults_to_hosted_when_key_absent(tmp_path: Path) -> None:
    """No DEVKIT_CI_RUNNER => a valid JSON array holding the hosted default."""
    outputs = _run_resolve(tmp_path, "DEVKIT_MODE=direnv\n")
    assert json.loads(outputs["runner-json"]) == [HOSTED_DEFAULT]


def test_runner_json_defaults_when_no_manifest(tmp_path: Path) -> None:
    """No .vig-os at all still yields the hosted default array.

    The default `both` mode then errors on the missing tag (an unrelated
    production error path), but runner-json is emitted before that exit.
    """
    outputs = _run_resolve(tmp_path, None, check=False)
    assert json.loads(outputs["runner-json"]) == [HOSTED_DEFAULT]


def test_runner_json_single_label(tmp_path: Path) -> None:
    """A single custom label is emitted as a one-element JSON array."""
    outputs = _run_resolve(tmp_path, "DEVKIT_MODE=direnv\nDEVKIT_CI_RUNNER=my-runner\n")
    assert json.loads(outputs["runner-json"]) == ["my-runner"]


def test_runner_json_multi_label(tmp_path: Path) -> None:
    """A comma-separated label list becomes a JSON array, whitespace trimmed."""
    outputs = _run_resolve(
        tmp_path,
        "DEVKIT_MODE=direnv\nDEVKIT_CI_RUNNER=self-hosted, linux, x64, meatgrinder\n",
    )
    assert json.loads(outputs["runner-json"]) == [
        "self-hosted",
        "linux",
        "x64",
        "meatgrinder",
    ]


@pytest.mark.parametrize("mode", ["direnv", "both"])
def test_runner_json_emitted_in_every_mode(tmp_path: Path, mode: str) -> None:
    """runner-json is emitted regardless of delivery mode."""
    manifest = (
        f"DEVKIT_MODE={mode}\nDEVKIT_VERSION=1.2.3\nDEVKIT_CI_RUNNER=self-hosted\n"
    )
    outputs = _run_resolve(tmp_path, manifest)
    assert json.loads(outputs["runner-json"]) == ["self-hosted"]
