"""Release-pin upgrade tests using the hotfix container boundary stand-in.

The stand-in executes the real scaffold on the host; unexpected runtime calls
are recorded so the policy assertions retain their original coverage.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL = REPO_ROOT / "install.sh"


def _stub(path: Path, body: str) -> None:
    path.write_text(f"#!/usr/bin/env bash\n{body}\n", encoding="utf-8")
    path.chmod(0o755)


def _runtime_stubs(tmp_path: Path, *, working: bool) -> tuple[Path, Path]:
    """Replay the container scaffold without requiring a container daemon."""
    assert not working
    bindir = tmp_path / "bin"
    bindir.mkdir()
    marker = tmp_path / "runtime-called"
    _stub(
        bindir / "docker",
        f'''case "$1" in
    info|pull|image) exit 0 ;;
    run)
        shift
        while [ "$#" -gt 0 ]; do
            case "$1" in
                --rm) shift ;;
                -e) export "$2"; shift 2 ;;
                -v) export WORKSPACE_DIR="${{2%:/workspace}}"; shift 2 ;;
                *) break ;;
            esac
        done
        shift
        if [ "$1" = /root/assets/init-workspace.sh ]; then
            shift
            export TEMPLATE_DIR="{REPO_ROOT}/assets/workspace"
            exec bash "{REPO_ROOT}/assets/init-workspace.sh" "$@"
        fi ;;
esac
echo "$*" >> "{marker}"
exit 99''',
    )
    _stub(bindir / "podman", f'echo "$*" >> "{marker}"; exit 99')
    return bindir, marker


def _nix_stub(bindir: Path) -> None:
    _stub(bindir / "nix", f'echo "$*" >> "{bindir}/nix.log"')


def _env(bindir: Path) -> dict[str, str]:
    return {**os.environ, "PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}"}


def _project(tmp_path: Path, mode: str) -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".vig-os").write_text(f"DEVKIT_MODE={mode}\n", encoding="utf-8")
    return project


@pytest.mark.parametrize("separator", ["?ref=", "/"])
@pytest.mark.parametrize(
    ("ref", "previous", "knob", "advances", "reason"),
    [
        ("1.2.2", "1.2.2", "", True, "advanced pinned input"),
        ("1.2.2", "1.2.2", "false", False, "explicit opt-out"),
        ("1.2.1", "1.2.2", "", False, "not in lockstep"),
        ("1.2.1", "1.2.2", "true", True, "advanced pinned input"),
        ("1.2.3", "1.2.3", "", False, "already pinned"),
    ],
)
def test_release_pin_upgrade_policy(
    tmp_path: Path,
    ref: str,
    previous: str,
    knob: str,
    advances: bool,
    reason: str,
    separator: str,
) -> None:
    """Run the target installer and real scaffold; mirror CI's pin lockstep gate."""
    bindir, marker = _runtime_stubs(tmp_path, working=False)
    _nix_stub(bindir)
    project = _project(tmp_path, "direnv")
    manifest = project / ".vig-os"
    manifest.write_text(
        f"DEVKIT_MODE=direnv\nDEVKIT_VERSION={previous}\n"
        f"DEVKIT_FLAKE_PIN_ADVANCE={knob}\n",
        encoding="utf-8",
    )
    (project / "flake.nix").write_text(
        f'{{ inputs = {{\n  vigos.url = "github:vig-os/devkit{separator}{ref}";\n}}; }}\n',
        encoding="utf-8",
    )
    (project / "flake.lock").write_text("{}\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    proc = subprocess.run(
        [
            "bash",
            str(INSTALL),
            "--force",
            "--skip-preflight",
            "--version",
            "1.2.3",
            str(project),
        ],
        env={**_env(bindir), "TMPDIR": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out
    lines = [line for line in out.splitlines() if line.startswith("flake-bump:")]
    assert len(lines) == 1 and reason in lines[0], out
    assert "DEVKIT_VERSION=1.2.3" in manifest.read_text()
    assert f"DEVKIT_FLAKE_PIN_ADVANCE={knob}\n" in manifest.read_text()
    expected = "1.2.3" if advances else ref
    assert f'{separator}{expected}"' in (project / "flake.nix").read_text()
    if advances:
        assert "flake update vigos" in (bindir / "nix.log").read_text()
        # CI rejects a release ref that differs from the scaffold version.
        assert f"DEVKIT_VERSION={expected}" in manifest.read_text()
    elif expected != "1.2.3":
        assert "hooks may fail and CI will reject" in out
        assert "DEVKIT_FLAKE_PIN_ADVANCE=true" in out
    assert not marker.exists()
