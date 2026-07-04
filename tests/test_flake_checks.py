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


def test_formatter_is_treefmt() -> None:
    """``flake.formatter.<system>`` must be the treefmt wrapper (so ``nix fmt`` works).

    treefmt-nix unifies the per-language formatters (nixfmt, ruff-format, taplo)
    behind one ``nix fmt`` entrypoint; the wrapper derivation is named ``treefmt``.
    """
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
    assert "treefmt" in result.stdout.strip(), (
        f"formatter is not treefmt: {result.stdout.strip()!r}"
    )


def test_checks_output_exposes_quality_gates() -> None:
    """``flake.checks.<system>`` must expose the lightweight quality gates.

    ``nix flake check`` on a flake with no ``checks`` output trivially succeeds,
    so guard the actual gate: assert the ``checks`` attrset names the treefmt
    formatting check, the dead-code (deadnix) and lint (statix) Nix gates, the
    dev-shell build, and the ``devShellTools`` eval.
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
    required = {
        "formatting",
        "deadnix",
        "statix",
        "devShell",
        "devShellTools",
        # git-hooks.nix runs the sandbox-pure subset of the pre-commit hooks as
        # a flake check, driven by the prek runner (#778).
        "pre-commit",
        # The ci homeConfigurations matrix builds as Tier-0 checks (#819) —
        # skipped only on x86_64-darwin (eval-only best-effort tier).
        "hm-minimal",
        "hm-full",
    }
    if system == "x86_64-darwin":
        required -= {"hm-minimal", "hm-full"}
    missing = required - names
    assert not missing, f"checks output is missing gates: {sorted(missing)}"


def test_nix_fast_build_driver_is_exposed() -> None:
    """``packages.<system>.nix-fast-build`` must stay exposed (the Tier-0 driver).

    CI runs ``nix run .#nix-fast-build`` to build every ``checks.<system>``
    derivation in parallel (the Tier-0 gate, #779). Guard the package so removing
    it is caught here rather than as a cryptic failure of the CI check step.
    """
    system = _current_system()
    result = subprocess.run(
        [
            "nix",
            "eval",
            "--raw",
            f"{REPO_ROOT}#packages.{system}.nix-fast-build.meta.mainProgram",
        ],
        capture_output=True,
        text=True,
        env=_nix_env(),
        timeout=600,
    )
    if result.returncode != 0:
        pytest.fail(
            "Failed to read packages.<system>.nix-fast-build:\n" + result.stderr
        )
    assert result.stdout.strip() == "nix-fast-build", (
        f"nix-fast-build package main program is unexpected: {result.stdout.strip()!r}"
    )


def test_install_app_is_runnable() -> None:
    """``flake.apps.<system>.install`` must expose a runnable installer program.

    Wraps ``install.sh`` so ``nix run .#install`` bootstraps a consumer project
    without a prior ``curl | bash``. Assert the app is well-formed (type ``app``
    with a program path) rather than executing it (which reaches the network).
    """
    system = _current_system()
    result = subprocess.run(
        [
            "nix",
            "eval",
            "--json",
            f"{REPO_ROOT}#apps.{system}.install",
            "--apply",
            "a: { inherit (a) type; hasProgram = a ? program; }",
        ],
        capture_output=True,
        text=True,
        env=_nix_env(),
        timeout=600,
    )
    if result.returncode != 0:
        pytest.fail("Failed to read apps.<system>.install:\n" + result.stderr)
    app = json.loads(result.stdout)
    assert app["type"] == "app", f"install app has wrong type: {app!r}"
    assert app["hasProgram"], "install app has no program attribute"


def test_toolchain_modules_are_exposed() -> None:
    """``nixosModules.default`` and ``homeManagerModules.default`` must exist.

    They expose the shared toolchain (``devTools``) as importable NixOS /
    home-manager config. Both are module functions, so assert their presence and
    that they evaluate to functions rather than converting them to JSON.
    """
    for output in ("nixosModules", "homeManagerModules"):
        result = subprocess.run(
            [
                "nix",
                "eval",
                "--json",
                f"{REPO_ROOT}#{output}",
                "--apply",
                "m: { hasDefault = m ? default; isImportable = "
                "builtins.isFunction m.default || builtins.isPath m.default; }",
            ],
            capture_output=True,
            text=True,
            env=_nix_env(),
            timeout=600,
        )
        if result.returncode != 0:
            pytest.fail(f"Failed to read {output}:\n" + result.stderr)
        info = json.loads(result.stdout)
        assert info["hasDefault"], f"{output} is missing a default module"
        # vigos home modules are exported as *paths* (the module system dedups
        # path imports, so `default` + a single module never double-declare
        # options); the NixOS module stays an inline function. Both import.
        assert info["isImportable"], f"{output}.default is not importable"


HM_MODULES = {"default", "packages", "shell", "multiplexer", "cli", "direnv", "git"}
HM_SYSTEMS = ("x86_64-linux", "aarch64-linux", "aarch64-darwin", "x86_64-darwin")


def test_vigos_home_module_set_is_exposed() -> None:
    """``homeManagerModules`` must expose the full vigos.* module set (#818).

    ``default`` is the umbrella importing every module (each disabled by
    default); the per-concern modules are individually importable. All are
    path-or-function modules.
    """
    result = subprocess.run(
        [
            "nix",
            "eval",
            "--json",
            f"{REPO_ROOT}#homeManagerModules",
            "--apply",
            "m: { names = builtins.attrNames m; importable = builtins.all "
            "(n: builtins.isPath m.${n} || builtins.isFunction m.${n}) "
            "(builtins.attrNames m); }",
        ],
        capture_output=True,
        text=True,
        env=_nix_env(),
        timeout=600,
    )
    if result.returncode != 0:
        pytest.fail("Failed to read homeManagerModules:\n" + result.stderr)
    info = json.loads(result.stdout)
    missing = HM_MODULES - set(info["names"])
    assert not missing, f"homeManagerModules is missing: {sorted(missing)}"
    assert info["importable"], "a homeManagerModules entry is not importable"


def test_home_modules_alias_matches() -> None:
    """``homeModules`` (newer convention) must mirror ``homeManagerModules``."""
    names: dict[str, list[str]] = {}
    for output in ("homeManagerModules", "homeModules"):
        result = subprocess.run(
            [
                "nix",
                "eval",
                "--json",
                f"{REPO_ROOT}#{output}",
                "--apply",
                "builtins.attrNames",
            ],
            capture_output=True,
            text=True,
            env=_nix_env(),
            timeout=600,
        )
        if result.returncode != 0:
            pytest.fail(f"Failed to read {output}:\n" + result.stderr)
        names[output] = json.loads(result.stdout)
    assert names["homeModules"] == names["homeManagerModules"], (
        f"homeModules alias diverges: {names!r}"
    )


def test_home_configurations_matrix() -> None:
    """The synthetic-ci homeConfigurations matrix must cover all systems (#819).

    ``ci-{minimal,full}-<system>`` for every supported system, including
    x86_64-darwin (which evaluates but is never built — best-effort tier).
    """
    result = subprocess.run(
        [
            "nix",
            "eval",
            "--json",
            f"{REPO_ROOT}#homeConfigurations",
            "--apply",
            "builtins.attrNames",
        ],
        capture_output=True,
        text=True,
        env=_nix_env(),
        timeout=600,
    )
    if result.returncode != 0:
        pytest.fail("Failed to read homeConfigurations:\n" + result.stderr)
    names = set(json.loads(result.stdout))
    expected = {
        f"ci-{profile}-{system}"
        for profile in ("minimal", "full")
        for system in HM_SYSTEMS
    }
    missing = expected - names
    assert not missing, f"homeConfigurations matrix is missing: {sorted(missing)}"


def test_home_configuration_evaluates_end_to_end() -> None:
    """A matrix leg must evaluate through the module system (cheap smoke)."""
    result = subprocess.run(
        [
            "nix",
            "eval",
            "--raw",
            f'{REPO_ROOT}#homeConfigurations."ci-minimal-x86_64-linux"'
            ".config.home.stateVersion",
        ],
        capture_output=True,
        text=True,
        env=_nix_env(),
        timeout=600,
    )
    if result.returncode != 0:
        pytest.fail("ci-minimal-x86_64-linux does not evaluate:\n" + result.stderr)
    assert result.stdout.strip() == "26.05"


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
