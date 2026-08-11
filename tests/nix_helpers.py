"""Shared helpers for tests that drive Nix (eval / develop / build).

Single home for the nix invocation environment, the current-system probe, and
the eval-to-JSON wrapper that the flake test modules previously each carried a
private copy of (#1413).
"""

from __future__ import annotations

import functools
import json
import os
import subprocess
from pathlib import Path

import pytest

# Repository root (tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parent.parent


def nix_env() -> dict[str, str]:
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


@functools.cache
def current_system() -> str:
    """The Nix system double for the host (e.g. x86_64-linux). Cached per run."""
    result = subprocess.run(
        ["nix", "eval", "--raw", "--impure", "--expr", "builtins.currentSystem"],
        capture_output=True,
        text=True,
        env=nix_env(),
        timeout=120,
    )
    if result.returncode != 0:
        pytest.fail("Failed to resolve builtins.currentSystem:\n" + result.stderr)
    return result.stdout.strip()


def nix_eval_json(installable: str, *, apply: str | None = None, timeout: int = 600):
    """``nix eval --json <installable> [--apply <fn>]`` -> parsed JSON.

    Fails the calling test with stderr attached on a non-zero exit.
    """
    cmd = ["nix", "eval", "--json", installable]
    if apply is not None:
        cmd += ["--apply", apply]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=nix_env(),
        timeout=timeout,
    )
    if result.returncode != 0:
        pytest.fail(f"nix eval failed for {installable}:\n" + result.stderr)
    return json.loads(result.stdout)


def nix_eval_raw(installable: str, *, timeout: int = 600) -> str:
    """``nix eval --raw <installable>`` -> stripped stdout."""
    result = subprocess.run(
        ["nix", "eval", "--raw", installable],
        capture_output=True,
        text=True,
        env=nix_env(),
        timeout=timeout,
    )
    if result.returncode != 0:
        pytest.fail(f"nix eval failed for {installable}:\n" + result.stderr)
    return result.stdout.strip()


def flake_expr(body: str, *, system: str | None = None) -> str:
    """Build a ``let flake = getFlake …; pkgs = …; in <body>`` expression.

    ``pkgs`` is only bound when ``system`` is given (it forces an import of
    the flake's nixpkgs input for that system).
    """
    lines = [f'let flake = builtins.getFlake "path:{REPO_ROOT}";']
    if system is not None:
        lines.append(
            f'    pkgs = import flake.inputs.nixpkgs {{ system = "{system}"; }};'
        )
    lines.append(f"in {body}")
    return "\n".join(lines)
