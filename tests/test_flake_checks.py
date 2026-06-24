"""Flake quality-gate tests: formatter + ``nix flake check`` (issue #674).

The flake is the toolchain SSoT but was itself ungated. These tests assert the
two quality gates the flake now exposes:

* ``flake.formatter.<system>`` is ``nixfmt`` (so ``nix fmt`` formats nix files),
* ``nix flake check`` succeeds (it evaluates the flake and runs the lightweight
  ``checks`` — a ``nixfmt --check`` format gate, a dev-shell build, and an eval
  of ``devShellTools``).

The suite is skipped automatically when ``nix`` is not on PATH (mirroring the
dev-shell parity test) so it never breaks unrelated CI lanes.

Refs: #674
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

# Repository root (two levels up: tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.skipif(
    shutil.which("nix") is None,
    reason="nix is not installed; flake quality-gate tests require Nix",
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


def test_formatter_is_nixfmt() -> None:
    """``flake.formatter.<system>`` must resolve to nixfmt (so ``nix fmt`` works)."""
    system = _current_system()
    result = subprocess.run(
        ["nix", "eval", "--raw", f"{REPO_ROOT}#formatter.{system}.name"],
        capture_output=True,
        text=True,
        env=_nix_env(),
        timeout=600,
    )
    if result.returncode != 0:
        pytest.fail("Failed to read formatter.<system>.name:\n" + result.stderr)
    assert "nixfmt" in result.stdout.strip(), (
        f"formatter is not nixfmt: {result.stdout.strip()!r}"
    )


def test_checks_output_exposes_format_and_devshell_gates() -> None:
    """``flake.checks.<system>`` must expose the lightweight quality gates.

    ``nix flake check`` on a flake with no ``checks`` output trivially succeeds,
    so guard the actual gate: assert the ``checks`` attrset names the format
    check, the dev-shell build, and the ``devShellTools`` eval.
    """
    system = _current_system()
    result = subprocess.run(
        [
            "nix",
            "eval",
            "--json",
            f"{REPO_ROOT}#checks.{system}",
            "--apply",
            "builtins.attrNames",
        ],
        capture_output=True,
        text=True,
        env=_nix_env(),
        timeout=600,
    )
    if result.returncode != 0:
        pytest.fail("Failed to read checks.<system> attr names:\n" + result.stderr)
    names = set(json.loads(result.stdout))
    required = {"format", "devShell", "devShellTools"}
    missing = required - names
    assert not missing, f"checks output is missing gates: {sorted(missing)}"


def test_flake_check_succeeds() -> None:
    """``nix flake check`` evaluates the flake and runs the lightweight checks."""
    result = subprocess.run(
        ["nix", "flake", "check", "--accept-flake-config", str(REPO_ROOT)],
        capture_output=True,
        text=True,
        env=_nix_env(),
        timeout=1800,
    )
    assert result.returncode == 0, (
        "nix flake check failed:\n" + result.stdout + "\n" + result.stderr
    )
