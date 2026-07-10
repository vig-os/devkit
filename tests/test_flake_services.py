"""Local dev-services gates: ``mkProjectServices`` + the MinIO/Postgres PoC (#795).

ADR-nix-devenv-strategy (#794) adopts ``process-compose`` + ``services-flake``
as the org default for local dev services. These tests gate the implementation:

* ``lib.mkProjectServices`` is exported alongside ``mkProjectShell``/``devTools``,
* ``apps.<system>.services`` is a runnable app (``nix run .#services``),
* ``packages.<system>.services`` is exposed without clobbering the Linux-only
  image packages (the ``packages`` attrset is restructured out of the
  ``optionalAttrs`` guard, which a shallow ``//`` merge would otherwise eat),
* the PoC actually boots SeaweedFS (S3) + Postgres as native processes — no
  Docker or Podman daemon — and tears down cleanly.

The issue AC named MinIO, but nixpkgs marks minio abandoned upstream with
unfixed CVEs, so the PoC ships the maintained S3-compatible SeaweedFS instead
(recorded on #795 and in docs/NIX.md).

The suite is skipped automatically when ``nix`` is not on PATH (mirroring
``test_flake_checks.py``) so it never breaks unrelated lanes.

Refs: #795
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

# Repository root (two levels up: tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parent.parent

# Ports the PoC binds (flake.nix servicesPoC): postgres is non-default to
# dodge a CI runner's own postgres (5432); 8333 is SeaweedFS's stock S3 port.
POC_POSTGRES_PORT = 5433
POC_S3_PORT = 8333

pytestmark = pytest.mark.skipif(
    shutil.which("nix") is None,
    reason="nix is not installed; services PoC tests require Nix",
)


def _nix_env() -> dict[str, str]:
    """Environment for nix invocations with flakes enabled and the public cache."""
    env = os.environ.copy()
    env.setdefault(
        "NIX_CONFIG",
        "experimental-features = nix-command flakes\n"
        "extra-substituters = https://vig-os.cachix.org\n"
        "extra-trusted-public-keys = "
        "vig-os.cachix.org-1:yoOYRi3bvnM6ThxO0joLt7vtzhTfkq3r6jykeUMg7Bk=",
    )
    return env


def _current_system() -> str:
    """The Nix system double for the host (e.g. x86_64-linux)."""
    result = subprocess.run(
        ["nix", "eval", "--raw", "--impure", "--expr", "builtins.currentSystem"],
        capture_output=True,
        text=True,
        env=_nix_env(),
        timeout=120,
    )
    if result.returncode != 0:
        pytest.fail("Failed to resolve builtins.currentSystem:\n" + result.stderr)
    return result.stdout.strip()


def _free_port() -> int:
    """An ephemeral TCP port that is free right now (for process-compose's API)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_lib_exports_mk_project_services() -> None:
    """``lib`` must export ``mkProjectServices`` beside the existing helpers.

    Consumers reach the services builder exactly like ``mkProjectShell``:
    ``vigos.lib.mkProjectServices { inherit pkgs; modules = [ ... ]; }`` — with
    no extra flake inputs downstream (this flake's lock carries
    process-compose-flake and services-flake).
    """
    result = subprocess.run(
        [
            "nix",
            "eval",
            "--json",
            f"{REPO_ROOT}#lib",
            "--apply",
            "builtins.attrNames",
        ],
        capture_output=True,
        text=True,
        env=_nix_env(),
        timeout=600,
    )
    if result.returncode != 0:
        pytest.fail("Failed to read lib attr names:\n" + result.stderr)
    names = set(json.loads(result.stdout))
    required = {"mkProjectShell", "mkProjectServices", "devTools"}
    missing = required - names
    assert not missing, f"lib output is missing helpers: {sorted(missing)}"


def test_services_app_is_runnable() -> None:
    """``apps.<system>.services`` must be a well-formed app (``nix run .#services``).

    Mirrors the ``install`` app gate: assert shape (type ``app`` + program),
    not execution — booting is covered by the dedicated PoC test below.
    """
    system = _current_system()
    result = subprocess.run(
        [
            "nix",
            "eval",
            "--json",
            f"{REPO_ROOT}#apps.{system}.services",
            "--apply",
            "a: { inherit (a) type; hasProgram = a ? program; }",
        ],
        capture_output=True,
        text=True,
        env=_nix_env(),
        timeout=600,
    )
    if result.returncode != 0:
        pytest.fail("Failed to read apps.<system>.services:\n" + result.stderr)
    app = json.loads(result.stdout)
    assert app["type"] == "app", f"services app has wrong type: {app!r}"
    assert app["hasProgram"], "services app has no program attribute"


def test_services_package_exposed_without_clobbering_linux_packages() -> None:
    """``packages.<system>.services`` exists and the image packages survive.

    ``packages`` used to live entirely inside a Linux-only ``optionalAttrs``
    shallow merge; adding a cross-platform ``services`` package means
    restructuring that guard. Guard the restructure: on ``*-linux`` the image
    attrs (``devkitImage``/``devkitImageEnv``/``vulnix``/
    ``nix-fast-build``) must still be present alongside ``services``.
    """
    system = _current_system()
    result = subprocess.run(
        [
            "nix",
            "eval",
            "--json",
            f"{REPO_ROOT}#packages.{system}",
            "--apply",
            "builtins.attrNames",
        ],
        capture_output=True,
        text=True,
        env=_nix_env(),
        timeout=600,
    )
    if result.returncode != 0:
        pytest.fail("Failed to read packages.<system> attr names:\n" + result.stderr)
    names = set(json.loads(result.stdout))
    assert "services" in names, f"packages.{system} has no services package: {names}"
    if system.endswith("-linux"):
        required = {
            "devkitImage",
            "devkitImageEnv",
            "vulnix",
            "nix-fast-build",
        }
        missing = required - names
        assert not missing, (
            f"Linux-only image packages were clobbered by the packages "
            f"restructure: {sorted(missing)}"
        )


def _wait_for_tcp(port: int, deadline: float) -> None:
    """Block until 127.0.0.1:<port> accepts a TCP connection or the deadline."""
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2):
                return
        except OSError:
            time.sleep(1)
    pytest.fail(f"Service on 127.0.0.1:{port} did not accept a connection in time")


def _wait_for_http_ok(url: str, deadline: float) -> None:
    """Block until GET <url> returns HTTP 200 or the deadline passes."""
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except urllib.error.URLError, OSError:
            pass
        time.sleep(1)
    pytest.fail(f"GET {url} did not return 200 in time")


def test_services_poc_boots_s3_and_postgres(tmp_path: Path) -> None:
    """The PoC boots SeaweedFS + Postgres as native processes, teardown clean.

    This is the acceptance test for the daemonless promise: it builds
    ``packages.<system>.services`` (process-compose wrapper generated by
    services-flake), launches it headless (``--tui=false``) in a temp cwd
    (services-flake writes its state under ``./data``), and polls Postgres's
    TCP socket and the SeaweedFS S3 gateway's health endpoint. No podman or
    docker fixture is used anywhere — that absence is itself the "no container
    daemon" assertion. The printed timings feed the #795 eval-cost/timing note.
    """
    build_start = time.monotonic()
    result = subprocess.run(
        [
            "nix",
            "build",
            "--no-link",
            "--print-out-paths",
            "--accept-flake-config",
            f"{REPO_ROOT}#services",
        ],
        capture_output=True,
        text=True,
        env=_nix_env(),
        timeout=1800,
    )
    if result.returncode != 0:
        pytest.fail("Failed to build the services PoC package:\n" + result.stderr)
    out_path = result.stdout.strip().splitlines()[-1]
    build_seconds = time.monotonic() - build_start

    api_port = _free_port()
    boot_start = time.monotonic()
    proc = subprocess.Popen(
        [f"{out_path}/bin/services", "--tui=false", "--port", str(api_port)],
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        deadline = time.monotonic() + 120
        _wait_for_tcp(POC_POSTGRES_PORT, deadline)
        _wait_for_http_ok(f"http://127.0.0.1:{POC_S3_PORT}/healthz", deadline)
        ready_seconds = time.monotonic() - boot_start
        # Raw data for the docs/NIX.md timing note (visible with pytest -s).
        print(
            f"\nservices PoC timing: build/substitute {build_seconds:.1f}s, "
            f"time-to-ready {ready_seconds:.1f}s"
        )
        assert proc.poll() is None, "process-compose exited before teardown"
    finally:
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=30)
