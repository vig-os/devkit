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

from tests.conftest import disable_git_auto_maintenance

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


def _nix_stub(bindir: Path) -> None:
    """`nix` stand-in: metadata -> this checkout, develop -> run the command, rest logged."""
    log = bindir / "nix.log"
    _stub(
        bindir / "nix",
        f"""args=" $* "
case "$args" in
  *" flake metadata "*) printf '%s' '{json.dumps({"path": str(REPO_ROOT)})}' ;;
  *" develop "*)
    # Like the real dev-shell hook: configure whatever repo it starts in.
    pwd > "{bindir}/develop.cwd"
    git rev-parse --git-dir >/dev/null 2>&1 && git config core.hooksPath devkit-hooks
    while [ "$1" != "-c" ]; do shift; done; shift; exec "$@" ;;
  *) echo "$*" >> "{log}" ;;
esac""",
    )


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
    _nix_stub(bindir)
    project = _project(tmp_path, "direnv")
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c"]
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    disable_git_auto_maintenance(project)

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


def test_latest_resolves_from_the_manifest_pin(tmp_path: Path) -> None:
    """An upgrade with no --version re-applies the repo's own pin (dry-run shows it)."""
    bindir, _ = _runtime_stubs(tmp_path, working=False)
    project = _project(tmp_path, "direnv")
    (project / ".vig-os").write_text(
        "DEVKIT_MODE=direnv\nDEVKIT_VERSION=1.7.0\n", encoding="utf-8"
    )
    proc = subprocess.run(
        ["bash", str(INSTALL), "--dry-run", "--skip-preflight", str(project)],
        env=_env(bindir),
        capture_output=True,
        text=True,
        check=False,
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out
    assert "github:vig-os/devkit/1.7.0" in out and "VIG_OS_VERSION=1.7.0" in out


def test_fresh_latest_resolves_the_newest_release_tag(tmp_path: Path) -> None:
    """No manifest pin: the highest X.Y.Z tag on the devkit remote (no rc, no 'latest')."""
    remote = tmp_path / "remote"
    subprocess.run(["git", "init", "-q", str(remote)], check=True)
    disable_git_auto_maintenance(remote)
    subprocess.run(
        [
            "git",
            "-C",
            str(remote),
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@t",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "x",
        ],
        check=True,
    )
    for tag in ("1.9.0", "1.10.0", "1.10.1-rc1", "1.2.3", "latest"):
        subprocess.run(
            ["git", "-C", str(remote), "-c", "tag.gpgSign=false", "tag", tag],
            check=True,
        )
    bindir, _ = _runtime_stubs(tmp_path, working=False)
    project = tmp_path / "fresh"
    project.mkdir()
    env = _env(bindir) | {
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "url." + str(remote) + ".insteadOf",
        "GIT_CONFIG_VALUE_0": "https://github.com/vig-os/devkit",
    }
    proc = subprocess.run(
        [
            "bash",
            str(INSTALL),
            "--dry-run",
            "--skip-preflight",
            "--mode",
            "direnv",
            str(project),
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out
    assert "github:vig-os/devkit/1.10.0" in out


def test_unresolvable_latest_is_a_clear_error(tmp_path: Path) -> None:
    bindir, marker = _runtime_stubs(tmp_path, working=False)
    project = tmp_path / "fresh"
    project.mkdir()
    env = _env(bindir) | {
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "url." + str(tmp_path / "nowhere") + ".insteadOf",
        "GIT_CONFIG_VALUE_0": "https://github.com/vig-os/devkit",
    }
    proc = subprocess.run(
        [
            "bash",
            str(INSTALL),
            "--dry-run",
            "--skip-preflight",
            "--mode",
            "direnv",
            str(project),
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "Could not resolve the latest devkit release" in proc.stderr
    assert not marker.exists()


def test_runtime_flag_is_ignored_with_a_warning_in_direnv_mode(tmp_path: Path) -> None:
    bindir, marker = _runtime_stubs(tmp_path, working=False)
    proc = subprocess.run(
        [
            "bash",
            str(INSTALL),
            "--dry-run",
            "--skip-preflight",
            "--docker",
            "--version",
            "1.2.3",
            str(_project(tmp_path, "direnv")),
        ],
        env=_env(bindir),
        capture_output=True,
        text=True,
        check=False,
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out
    assert "--docker is ignored in direnv mode" in out
    assert not marker.exists()


def test_invalid_version_is_rejected(tmp_path: Path) -> None:
    bindir, _ = _runtime_stubs(tmp_path, working=False)
    proc = subprocess.run(
        [
            "bash",
            str(INSTALL),
            "--dry-run",
            "--skip-preflight",
            "--version",
            "1.2/../x",
            str(_project(tmp_path, "direnv")),
        ],
        env=_env(bindir),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "Invalid devkit version" in proc.stderr


@pytest.mark.skipif(
    not (_gnu_sed() and shutil.which("rsync") and shutil.which("jq")),
    reason="the scaffold needs GNU sed, rsync and jq on PATH (Linux CI / dev shell)",
)
def test_direnv_upgrade_reports_the_flake_bump_line(tmp_path: Path) -> None:
    """devkit-upgrade.yml greps `^flake-bump:` from install.sh's output."""
    bindir, marker = _runtime_stubs(tmp_path, working=False)
    _nix_stub(bindir)
    project = _project(tmp_path, "direnv")
    (project / "flake.nix").write_text(
        '{\n  inputs = {\n    vigos.url = "github:vig-os/devkit";\n  };\n}\n',
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
        env=_env(bindir),
        capture_output=True,
        text=True,
        check=False,
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out
    flake_bump = [ln for ln in out.splitlines() if ln.startswith("flake-bump:")]
    assert len(flake_bump) == 1 and "advanced input 'vigos'" in flake_bump[0], out
    assert "flake update vigos" in (bindir / "nix.log").read_text(encoding="utf-8")
    assert not marker.exists()


def test_smoke_lane_installs_nix_and_drops_the_container_workarounds() -> None:
    """The direnv smoke lane scaffolds on the host (#1871): Nix first, no --docker."""
    text = (
        REPO_ROOT / "assets/smoke-test/.github/workflows/direnv-smoke.yml"
    ).read_text(encoding="utf-8")
    assert "--docker" not in text
    assert "chown -R" not in text
    assert text.index("name: Install Nix") < text.index(
        "name: Scaffold a throwaway direnv workspace"
    )


@pytest.mark.skipif(
    not (_gnu_sed() and shutil.which("rsync") and shutil.which("jq")),
    reason="the scaffold needs GNU sed, rsync and jq on PATH (Linux CI / dev shell)",
)
def test_dev_shell_never_starts_in_the_callers_repo(tmp_path: Path) -> None:
    """The dev-shell hooks act on their cwd: it must be the scratch dir, not the caller's."""
    bindir, _ = _runtime_stubs(tmp_path, working=False)
    _nix_stub(bindir)
    caller = tmp_path / "caller"
    caller.mkdir()
    subprocess.run(["git", "init", "-q", str(caller)], check=True)
    project = _project(tmp_path, "direnv")
    proc = subprocess.run(
        ["bash", str(INSTALL), "--skip-preflight", "--version", "1.2.3", str(project)],
        env=_env(bindir),
        cwd=caller,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    started_in = Path((bindir / "develop.cwd").read_text(encoding="utf-8").strip())
    assert started_in.resolve() != caller.resolve()
    hooks = subprocess.run(
        ["git", "-C", str(caller), "config", "core.hooksPath"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert hooks.stdout == "", "the caller's repo config was modified"


@pytest.mark.parametrize("mode", ["direnv", "devcontainer"])
def test_migration_environment_crosses_installer_boundary(
    tmp_path: Path, mode: str
) -> None:
    """Execute both installer paths; a runtime stand-in enforces isolation."""
    import re
    import shlex

    source = INSTALL.read_text(encoding="utf-8")
    match = re.search(r"UPGRADE_ENV_NAMES=\(\s*(.*?)\s*\)", source, re.S)
    assert match, "installer must define the migration allow-list once"
    names = match.group(1).split()
    assert len(names) == 6 and len(set(names)) == 6
    values = {name: f"value-{index}" for index, name in enumerate(names)}
    values["DEVKIT_UPGRADE_CONTEXT"] = "1"
    values["DEVKIT_UPGRADE_REPO_PRIVATE"] = "true"
    # Shell metacharacters must remain inert data, including on the container leg.
    values["DEVKIT_UPGRADE_LEGACY_RESOLVE_RUNNER"] = "$(touch should-not-exist) `false`"
    capture = tmp_path / "captured-env"
    src = tmp_path / "source"
    (src / "assets/workspace").mkdir(parents=True)
    (src / "assets/workspace/.vig-os").write_text("DEVKIT_VERSION={{IMAGE_TAG}}\n")
    probe = src / "assets/init-workspace.sh"
    probe.write_text(f"env > {shlex.quote(str(capture))}\n")
    bindir, _ = _runtime_stubs(tmp_path, working=True)
    _stub(
        bindir / "nix",
        f"""case " $* " in
  *" flake metadata "*) printf '%s' '{json.dumps({"path": str(src)})}' ;;
  *" develop "*) while [ "$1" != -c ]; do shift; done; shift; exec "$@" ;;
esac""",
    )
    _stub(
        bindir / "docker",
        f"""if [[ "$1" != run ]]; then exit 0; fi
shift
forwarded=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --rm) shift ;;
        -e) forwarded+=("$2"); shift 2 ;;
        -v) shift 2 ;;
        *) break ;;
    esac
done
exec env -i PATH="$PATH" "${{forwarded[@]}}" bash {shlex.quote(str(probe))}""",
    )
    env = {**_env(bindir), **values, "DEVKIT_UPGRADE_UNLISTED": "must-not-cross"}
    proc = subprocess.run(
        [
            "bash",
            str(INSTALL),
            "--preview",
            "--skip-preflight",
            "--version",
            "1.2.3",
            "--docker",
            str(_project(tmp_path, mode)),
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    actual = dict(line.split("=", 1) for line in capture.read_text().splitlines())
    assert {name: actual.get(name) for name in names} == values
    assert "DEVKIT_UPGRADE_UNLISTED" not in actual
    assert not (tmp_path / "should-not-exist").exists()
