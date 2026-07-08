"""Auth-branch tests for the resolve-image action's accessibility probe.

The "Validate image accessibility" step logs in to ``ghcr.io`` before probing
the tag when a ``registry-token`` is supplied, and classifies a probe failure
into an actionable ``::error::`` annotation that distinguishes an auth/denied
failure from a genuinely missing tag. These tests extract that step's real
``run`` body from the action YAML and execute it against a stubbed ``docker``
so the branch logic is exercised without a registry or daemon.

Refs: #920
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
RESOLVE_IMAGE_ACTION = (
    REPO_ROOT / ".github" / "actions" / "resolve-image" / "action.yml"
)


def _probe_step_script() -> str:
    """The bash body of the action's 'Validate image accessibility' step."""
    action = yaml.safe_load(RESOLVE_IMAGE_ACTION.read_text(encoding="utf-8"))
    steps = action["runs"]["steps"]
    probe = next(s for s in steps if s.get("name") == "Validate image accessibility")
    return probe["run"]


def _write_docker_stub(
    bindir: Path, *, manifest_rc: int, manifest_stderr: str, login_rc: int = 0
) -> Path:
    """Install a fake ``docker`` on PATH.

    ``docker login`` touches a marker file (so tests can assert it ran) and
    exits ``login_rc``; ``docker manifest inspect`` prints ``manifest_stderr``
    to stderr and exits ``manifest_rc``.
    """
    marker = bindir / "login-called"
    stub = bindir / "docker"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        'if [[ "$1" == "login" ]]; then\n'
        "  cat >/dev/null\n"
        f'  touch "{marker}"\n'
        f"  exit {login_rc}\n"
        "fi\n"
        'if [[ "$1" == "manifest" ]]; then\n'
        f"  printf '%s' {manifest_stderr!r} >&2\n"
        f"  exit {manifest_rc}\n"
        "fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return marker


def _run_probe(
    tmp_path: Path,
    *,
    token: str,
    manifest_rc: int,
    manifest_stderr: str,
    login_rc: int = 0,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    bindir = tmp_path / "bin"
    bindir.mkdir()
    marker = _write_docker_stub(
        bindir,
        manifest_rc=manifest_rc,
        manifest_stderr=manifest_stderr,
        login_rc=login_rc,
    )
    result = subprocess.run(
        ["bash", "-c", _probe_step_script()],
        env={
            **os.environ,
            "PATH": f"{bindir}:{os.environ['PATH']}",
            "IMAGE_TAG": "0.4.0",
            "REGISTRY_TOKEN": token,
            "REGISTRY_USERNAME": "octocat",
        },
        capture_output=True,
        text=True,
        check=False,
    )
    return result, marker


def test_probe_success_is_quiet(tmp_path: Path) -> None:
    """A readable manifest returns success (public, anonymous path)."""
    result, marker = _run_probe(tmp_path, token="", manifest_rc=0, manifest_stderr="")
    assert result.returncode == 0, result.stderr
    assert not marker.exists()  # no login without a token


def test_probe_logs_in_when_token_present(tmp_path: Path) -> None:
    """A non-empty token triggers docker login before the probe."""
    result, marker = _run_probe(
        tmp_path, token="ghp_secret", manifest_rc=0, manifest_stderr=""
    )
    assert result.returncode == 0, result.stderr
    assert marker.exists()  # login ran


def test_probe_denied_reports_auth_error(tmp_path: Path) -> None:
    """A denied/unauthorized manifest failure maps to the auth ::error::."""
    result, _ = _run_probe(
        tmp_path,
        token="",
        manifest_rc=1,
        manifest_stderr="denied: requested access to the resource is denied",
    )
    assert result.returncode == 1
    assert "authentication required or denied" in result.stdout
    assert "GHCR_PULL_TOKEN" in result.stdout


def test_probe_missing_tag_reports_missing_error(tmp_path: Path) -> None:
    """A not-found manifest failure maps to the missing-tag ::error::."""
    result, _ = _run_probe(
        tmp_path,
        token="",
        manifest_rc=1,
        manifest_stderr="manifest unknown: manifest unknown",
    )
    assert result.returncode == 1
    assert "does not exist or is not readable" in result.stdout
    assert "authentication required or denied" not in result.stdout


def test_probe_failed_login_reports_auth_error(tmp_path: Path) -> None:
    """A failed docker login surfaces the auth ::error:: and stops."""
    result, marker = _run_probe(
        tmp_path,
        token="ghp_bad",
        manifest_rc=0,
        manifest_stderr="",
        login_rc=1,
    )
    assert result.returncode == 1
    assert marker.exists()
    assert "Failed to authenticate" in result.stdout
