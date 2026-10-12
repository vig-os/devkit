"""install.sh scaffolds in direnv mode without a container runtime (#1871).

direnv mode runs the pinned ``init-workspace.sh`` on the host from the devkit
flake source (``nix flake metadata`` -> ``assets/``, bake steps replayed), the
same replay as ci.yml's drift check (#1861). Container modes keep the image
path unchanged.

Refs: #1871
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL = REPO_ROOT / "install.sh"


def _stub(path: Path, body: str) -> None:
    path.write_text(f"#!/usr/bin/env bash\n{body}\n", encoding="utf-8")
    path.chmod(0o755)


def _runtime_stubs(tmp_path: Path, *, working: bool) -> tuple[Path, Path]:
    """docker/podman stubs on PATH. Returns (bin dir, marker file).

    ``working=False`` stubs record any call in the marker and fail, so a test
    proves a path never touched a container runtime.
    """
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    marker = tmp_path / "runtime-called"
    for name in ("docker", "podman"):
        if working:
            _stub(bindir / name, "exit 0")
        else:
            _stub(bindir / name, f'echo "$0 $*" >> "{marker}"; exit 99')
    return bindir, marker


def _env(bindir: Path) -> dict[str, str]:
    return {**os.environ, "PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}"}


def _project(tmp_path: Path, mode: str) -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".vig-os").write_text(f"DEVKIT_MODE={mode}\n", encoding="utf-8")
    return project


def _dry_run(project: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "bash",
            str(INSTALL),
            "--dry-run",
            "--skip-preflight",
            "--version",
            "1.2.3",
            str(project),
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_direnv_dry_run_plans_a_host_scaffold_without_a_runtime(
    tmp_path: Path,
) -> None:
    bindir, marker = _runtime_stubs(tmp_path, working=False)
    proc = _dry_run(_project(tmp_path, "direnv"), _env(bindir))
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out
    assert "nix flake metadata --json github:vig-os/devkit/1.2.3" in out
    assert "init-workspace.sh" in out and "--mode direnv" in out
    assert "no container runtime" in out
    assert "run --rm" not in out
    assert not marker.exists(), marker.read_text()


@pytest.mark.parametrize("mode", ["devcontainer", "both"])
def test_container_modes_still_plan_the_image_run(tmp_path: Path, mode: str) -> None:
    bindir, _ = _runtime_stubs(tmp_path, working=True)
    proc = _dry_run(_project(tmp_path, mode), _env(bindir))
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out
    assert "run --rm" in out
    assert "ghcr.io/vig-os/devcontainer:1.2.3" in out
    assert "nix flake metadata" not in out


def _gnu_sed() -> bool:
    out = subprocess.run(["sed", "--version"], capture_output=True, text=True)
    return out.returncode == 0 and "GNU" in out.stdout


@pytest.mark.skipif(
    not (_gnu_sed() and shutil.which("rsync") and shutil.which("jq")),
    reason="the scaffold needs GNU sed, rsync and jq on PATH (Linux CI / dev shell)",
)
def test_direnv_install_scaffolds_and_upgrades_on_the_host(tmp_path: Path) -> None:
    """Fresh scaffold, then --force upgrade: pinned, idempotent, no runtime call."""
    bindir, marker = _runtime_stubs(tmp_path, working=False)
    _stub(
        bindir / "nix",
        f"printf '%s' '{json.dumps({'path': str(REPO_ROOT)})}'",
    )
    project = _project(tmp_path, "direnv")
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c"]
    subprocess.run(["git", "init", "-q", str(project)], check=True)

    def install(*extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(INSTALL), "--skip-preflight", "--version", "1.2.3", *extra]
            + [str(project)],
            env=_env(bindir),
            capture_output=True,
            text=True,
            check=False,
        )

    first = install()
    assert first.returncode == 0, first.stdout + first.stderr
    manifest = (project / ".vig-os").read_text(encoding="utf-8")
    assert "DEVKIT_VERSION=1.2.3" in manifest
    assert not (project / ".devcontainer").exists()

    subprocess.run(["git", "-C", str(project), "add", "-A"], check=True)
    subprocess.run(
        [*git, "commit.gpgsign=false", "-C", str(project), "commit", "-qm", "scaffold"],
        check=True,
    )
    again = install("--force")
    assert again.returncode == 0, again.stdout + again.stderr
    status = subprocess.run(
        ["git", "-C", str(project), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert status.stdout == "", status.stdout
    assert not marker.exists(), marker.read_text()
    assert list(Path(os.environ.get("TMPDIR", "/tmp")).glob("devkit-scaffold.*")) == []


def test_direnv_install_requires_an_exact_release(tmp_path: Path) -> None:
    """`latest` is not a flake ref: refuse before fetching anything."""
    bindir, marker = _runtime_stubs(tmp_path, working=False)
    project = _project(tmp_path, "direnv")
    proc = subprocess.run(
        ["bash", str(INSTALL), "--skip-preflight", str(project)],
        env=_env(bindir),
        capture_output=True,
        text=True,
        check=False,
        stdin=subprocess.DEVNULL,
    )
    assert proc.returncode != 0
    assert not marker.exists()
