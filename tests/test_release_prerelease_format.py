"""Workflow tests: the pluggable pre-release format threads through the train.

Issue #1746: candidates were hard-coded as ``X.Y.Z-rc{N}`` inside
``release-core.yml``'s *Compute publish version* step. The format is now
selected with precedence

    ``release.yml`` dispatch input ``pre-release-format``
      > ``.vig-os`` ``DEVKIT_PRERELEASE_FORMAT``
      > ``rc{N}`` (the ``release-version`` CLI default)

and computed by the unit-tested ``release-version`` vig-utils CLI. The shape
tests pin the wiring; the executed tests run the step's real bash against a
stubbed ``git ls-remote`` and the real CLI, so a default dispatch is proven to
still produce the byte-identical ``X.Y.Z-rcN``.

Refs: #1746
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import TYPE_CHECKING

import pytest

from tests.workflow_scaffold import (
    WORKFLOWS,
    load_workflow,
    on_block,
    run_resolve_toolchain,
    scaffold,
    step_by_name,
)

if TYPE_CHECKING:
    from pathlib import Path

RELEASE = WORKFLOWS / "release.yml"
CORE = WORKFLOWS / "release-core.yml"


# ── shape: the input exists at every hop ──────────────────────────────────────


def test_release_dispatch_declares_pre_release_format_input() -> None:
    inputs = on_block(load_workflow(RELEASE))["workflow_dispatch"]["inputs"]
    spec = inputs["pre-release-format"]
    assert spec["type"] == "string"
    assert spec.get("required") is False
    # Empty default: the .vig-os key (then rc{N}) must be able to win.
    assert spec["default"] == ""


def test_release_threads_format_with_documented_precedence() -> None:
    core_with = load_workflow(RELEASE)["jobs"]["core"]["with"]
    expr = core_with["pre_release_format"]
    # dispatch input first, then the manifest key via resolve-toolchain.
    assert expr.index("inputs.pre-release-format") < expr.index(
        "needs.resolve-toolchain.outputs.prerelease-format"
    )
    resolve_out = load_workflow(RELEASE)["jobs"]["resolve-toolchain"]["outputs"]
    assert "prerelease-format" in resolve_out


def test_release_core_declares_pre_release_format_input() -> None:
    inputs = on_block(load_workflow(CORE))["workflow_call"]["inputs"]
    spec = inputs["pre_release_format"]
    assert spec["type"] == "string"
    assert spec["default"] == ""


def _compute_step() -> dict:
    steps = load_workflow(CORE)["jobs"]["validate"]["steps"]
    return step_by_name(steps, "Compute publish version")


def test_compute_step_delegates_to_release_version_cli() -> None:
    step = _compute_step()
    assert "release-version" in step["run"]
    # The -rc literal is gone from the computation (it lives in the CLI default).
    assert "-rc${" not in step["run"]
    assert step["env"]["PRE_RELEASE_FORMAT"] == "${{ inputs.pre_release_format }}"


# ── executed: the real step bash + the real CLI ───────────────────────────────


def _run_compute(
    tmp_path: Path,
    *,
    tags: list[str],
    fmt: str = "",
    kind: str = "candidate",
    rc_number: str = "",
    prefix: str = "",
    version: str = "1.2.3",
) -> tuple[subprocess.CompletedProcess[str], dict[str, str], str]:
    stub = tmp_path / "bin"
    stub.mkdir(exist_ok=True)
    calls = tmp_path / "git-calls"
    listing = tmp_path / "ls-remote"
    listing.write_text(
        "".join(f"deadbeef\trefs/tags/{t}\n" for t in tags), encoding="utf-8"
    )
    git = stub / "git"
    git.write_text(
        "#!/usr/bin/env bash\n"
        f'printf "%s\\n" "$*" >> "{calls}"\n'
        f'if [ "$1" = "ls-remote" ]; then cat "{listing}"; fi\n',
        encoding="utf-8",
    )
    git.chmod(0o755)
    assert shutil.which("release-version"), "release-version must be installed"

    out = tmp_path / "github-output"
    out.write_text("", encoding="utf-8")
    env = {
        **os.environ,
        "PATH": f"{stub}{os.pathsep}{os.environ['PATH']}",
        "GITHUB_OUTPUT": str(out),
        "VERSION": version,
        "RELEASE_KIND": kind,
        "INPUT_RC_NUMBER": rc_number,
        "TAG_PREFIX": prefix,
        "PRE_RELEASE_FORMAT": fmt,
    }
    proc = subprocess.run(
        ["bash", "-c", _compute_step()["run"]],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    outputs = dict(
        line.split("=", 1)
        for line in out.read_text(encoding="utf-8").splitlines()
        if "=" in line
    )
    git_calls = calls.read_text(encoding="utf-8") if calls.exists() else ""
    return proc, outputs, git_calls


def test_default_format_is_byte_identical_rc(tmp_path: Path) -> None:
    proc, outputs, _ = _run_compute(tmp_path, tags=["1.2.3-rc1", "1.2.3-rc21"])
    assert proc.returncode == 0, proc.stderr
    assert outputs["publish_version"] == "1.2.3-rc22"
    assert outputs["next_n"] == "22"


def test_alpha_format_produces_dotted_alpha_tag(tmp_path: Path) -> None:
    proc, outputs, _ = _run_compute(
        tmp_path, tags=[], fmt="alpha.{N}", prefix="v", version="0.1.0"
    )
    assert proc.returncode == 0, proc.stderr
    assert outputs["publish_version"] == "0.1.0-alpha.1"


def test_rc_number_pins_counter(tmp_path: Path) -> None:
    proc, outputs, _ = _run_compute(tmp_path, tags=["1.2.3-rc3"], rc_number="21")
    assert proc.returncode == 0, proc.stderr
    assert outputs["publish_version"] == "1.2.3-rc21"


def test_final_publishes_bare_version(tmp_path: Path) -> None:
    proc, outputs, _ = _run_compute(tmp_path, tags=["1.2.3-rc4"], kind="final")
    assert proc.returncode == 0, proc.stderr
    assert outputs["publish_version"] == "1.2.3"


def test_lowering_label_switch_fails_the_step(tmp_path: Path) -> None:
    proc, outputs, _ = _run_compute(tmp_path, tags=["1.2.3-rc21"], fmt="alpha.{N}")
    assert proc.returncode != 0
    assert "1.2.3-rc21" in proc.stdout + proc.stderr
    assert "publish_version" not in outputs


def test_discovery_lists_exact_version_and_its_prereleases(tmp_path: Path) -> None:
    """Both the final tag (monotonicity) and ``-*`` pre-releases are listed."""
    proc, _, git_calls = _run_compute(tmp_path, tags=[], prefix="v")
    assert proc.returncode == 0, proc.stderr
    assert "refs/tags/v1.2.3" in git_calls
    assert "refs/tags/v1.2.3-*" in git_calls


# ── .vig-os key: declared, resolved, persisted ────────────────────────────────


@pytest.mark.parametrize(
    ("manifest", "expected"),
    [
        ("DEVKIT_VERSION=1.2.3\nDEVKIT_MODE=bare\n", ""),
        (
            "DEVKIT_VERSION=1.2.3\nDEVKIT_MODE=bare\nDEVKIT_PRERELEASE_FORMAT=alpha.{N}\n",
            "alpha.{N}",
        ),
        (
            "DEVKIT_VERSION=1.2.3\nDEVKIT_MODE=bare\nDEVKIT_PRERELEASE_FORMAT='beta.{N}'\n",
            "beta.{N}",
        ),
    ],
    ids=["absent", "set", "quoted"],
)
def test_resolve_toolchain_emits_prerelease_format(
    tmp_path: Path, manifest: str, expected: str
) -> None:
    outputs = run_resolve_toolchain(tmp_path, manifest)
    assert outputs["prerelease-format"] == expected


def test_prerelease_format_persisted_across_rescaffold(tmp_path: Path) -> None:
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / ".vig-os").write_text(
        "DEVKIT_PRERELEASE_FORMAT=alpha.{N}\n", encoding="utf-8"
    )
    proc = scaffold(tmp_path, seed=seed, name="persist")
    assert proc.returncode == 0, proc.stderr
    text = (tmp_path / "persist" / ".vig-os").read_text(encoding="utf-8")
    assert "DEVKIT_PRERELEASE_FORMAT=alpha.{N}" in text.splitlines()
