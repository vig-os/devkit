"""Flake output-schema tests: formatter, checks attrset, apps, modules (#674).

The flake is the toolchain SSoT but was itself ungated. These tests assert the
output schema the CI gates rely on:

* ``flake.formatter.<system>`` is the treefmt wrapper (so ``nix fmt`` works),
* ``flake.checks.<system>`` names the quality gates (formatting, deadnix,
  statix, dev-shell build, devShellTools eval, the prek pre-commit gate and
  the home-manager CI matrix),
* the ``install`` app, ``nix-fast-build`` driver, templates, and the NixOS /
  home-manager module sets stay exposed,
* ``nix flake check`` itself succeeds (deselected in CI, where nix-fast-build
  builds the same checks — see ci.yml).

The suite is skipped automatically when ``nix`` is not on PATH (mirroring the
dev-shell parity test) so it never breaks unrelated CI lanes.

Refs: #674
"""

from __future__ import annotations

import functools
import shutil
import subprocess

import pytest

from .nix_helpers import REPO_ROOT, current_system, nix_env, nix_eval_json

pytestmark = pytest.mark.skipif(
    shutil.which("nix") is None,
    reason="nix is not installed; flake quality-gate tests require Nix",
)


def test_formatter_is_treefmt() -> None:
    """``flake.formatter.<system>`` must be the treefmt wrapper (so ``nix fmt`` works).

    treefmt-nix unifies the per-language formatters (nixfmt, ruff-format, taplo)
    behind one ``nix fmt`` entrypoint; the wrapper derivation is named ``treefmt``.
    """
    system = current_system()
    result = subprocess.run(
        ["nix", "eval", "--raw", f"{REPO_ROOT}#formatter.{system}.name"],
        capture_output=True,
        text=True,
        env=nix_env(),
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
    system = current_system()
    names = set(
        nix_eval_json(f"{REPO_ROOT}#checks.{system}", apply="builtins.attrNames")
    )
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
    system = current_system()
    result = subprocess.run(
        [
            "nix",
            "eval",
            "--raw",
            f"{REPO_ROOT}#packages.{system}.nix-fast-build.meta.mainProgram",
        ],
        capture_output=True,
        text=True,
        env=nix_env(),
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
    system = current_system()
    app = nix_eval_json(
        f"{REPO_ROOT}#apps.{system}.install",
        apply="a: { inherit (a) type; hasProgram = a ? program; }",
    )
    assert app["type"] == "app", f"install app has wrong type: {app!r}"
    assert app["hasProgram"], "install app has no program attribute"


@functools.cache
def _module_set_info(output: str) -> dict:
    """One eval per module-set output: names, default presence, importability.

    Shared by the module-schema tests below so nixosModules/homeManagerModules/
    homeModules are each evaluated once per run (#1413).
    """
    return nix_eval_json(
        f"{REPO_ROOT}#{output}",
        apply=(
            "m: { names = builtins.attrNames m; "
            "hasDefault = m ? default; "
            "defaultImportable = builtins.isFunction (m.default or null) "
            "|| builtins.isPath (m.default or null); "
            "allImportable = builtins.all "
            "(n: builtins.isPath m.${n} || builtins.isFunction m.${n}) "
            "(builtins.attrNames m); }"
        ),
    )


def test_toolchain_modules_are_exposed() -> None:
    """``nixosModules.default`` and ``homeManagerModules.default`` must exist.

    They expose the shared toolchain (``devTools``) as importable NixOS /
    home-manager config. vigos home modules are exported as *paths* (the module
    system dedups path imports, so ``default`` + a single module never
    double-declare options); the NixOS module stays an inline function.
    """
    for output in ("nixosModules", "homeManagerModules"):
        info = _module_set_info(output)
        assert info["hasDefault"], f"{output} is missing a default module"
        assert info["defaultImportable"], f"{output}.default is not importable"


HM_MODULES = {
    "default",
    "packages",
    "shell",
    "multiplexer",
    "cli",
    "direnv",
    "git",
    "claude",
    "sesh",
    "ghdash",
    "editor",
}
HM_SYSTEMS = ("x86_64-linux", "aarch64-linux", "aarch64-darwin", "x86_64-darwin")


def test_vigos_home_module_set_is_exposed() -> None:
    """``homeManagerModules`` must expose the full vigos.* module set (#818).

    ``default`` is the umbrella importing every module (each disabled by
    default); the per-concern modules are individually importable. All are
    path-or-function modules.
    """
    info = _module_set_info("homeManagerModules")
    missing = HM_MODULES - set(info["names"])
    assert not missing, f"homeManagerModules is missing: {sorted(missing)}"
    assert info["allImportable"], "a homeManagerModules entry is not importable"


def test_home_modules_alias_matches() -> None:
    """``homeModules`` (newer convention) must mirror ``homeManagerModules``."""
    assert (
        _module_set_info("homeModules")["names"]
        == _module_set_info("homeManagerModules")["names"]
    ), "homeModules alias diverges from homeManagerModules"


def test_home_configurations_matrix() -> None:
    """The synthetic-ci homeConfigurations matrix must cover all systems (#819).

    ``ci-{minimal,full}-<system>`` for every supported system, including
    x86_64-darwin (which evaluates but is never built — best-effort tier).
    """
    names = set(
        nix_eval_json(f"{REPO_ROOT}#homeConfigurations", apply="builtins.attrNames")
    )
    expected = {
        f"ci-{profile}-{system}"
        for profile in ("minimal", "full")
        for system in HM_SYSTEMS
    }
    expected.add("demo")
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
        env=nix_env(),
        timeout=600,
    )
    if result.returncode != 0:
        pytest.fail("ci-minimal-x86_64-linux does not evaluate:\n" + result.stderr)
    assert result.stdout.strip() == "26.05"


@functools.cache
def _ci_full_config() -> dict:
    """One eval of the interesting ci-full-x86_64-linux config slice.

    Shared by the wave-1 (#821), claude-policy (#823) and wave-3 (#824) tests
    below — previously three separate evals of the same configuration (#1413).
    """
    return nix_eval_json(
        f'{REPO_ROOT}#homeConfigurations."ci-full-x86_64-linux".config',
        apply=(
            "c: { "
            "bash = c.programs.bash.enable; "
            "zsh = c.programs.zsh.enable; "
            "starship = c.programs.starship.enable; "
            "atuin = c.programs.atuin.enable; "
            "zoxide = c.programs.zoxide.enable; "
            "tmux = c.programs.tmux.enable; "
            "direnv = c.programs.direnv.enable; "
            "nixDirenv = c.programs.direnv.nix-direnv.enable; "
            "git = c.programs.git.enable; "
            "gh = c.programs.gh.enable; "
            "lazygit = c.programs.lazygit.enable; "
            "signingKey = c.programs.git.signing.key; "
            "secretsEnvDefault = c.vigos.shell.secretsEnv.enable; "
            "autoupdater = c.home.sessionVariables.DISABLE_AUTOUPDATER or null; "
            "workspaceFiles = c.vigos.claude.claudeMd.workspaceFiles; "
            "claudeEnabled = c.vigos.claude.enable; "
            "ghdash = c.programs.gh-dash.enable; "
            "neovim = c.programs.neovim.enable; "
            'seshToml = c.home.file ? ".config/sesh/sesh.toml"; '
            "seshSessions = c.vigos.sesh.sessions; "
            "}"
        ),
    )


def test_wave1_full_profile_config() -> None:
    """Wave-1 modules must materialize in the full ci profile (#821).

    Every wave-1 program enabled, git signing INACTIVE by default
    (signingKeyPath is null on fresh hosts — first commits must not fail),
    and the secretsEnv hook present but off by default.
    """
    cfg = _ci_full_config()
    enabled = [
        "bash",
        "zsh",
        "starship",
        "atuin",
        "zoxide",
        "tmux",
        "direnv",
        "nixDirenv",
        "git",
        "gh",
        "lazygit",
    ]
    off = [k for k in enabled if not cfg[k]]
    assert not off, f"wave-1 programs not enabled in full profile: {off}"
    assert cfg["signingKey"] is None, "git signing must be inactive by default"
    assert cfg["secretsEnvDefault"] is False, "secretsEnv must default off"


def test_claude_module_policy() -> None:
    """vigos.claude must honor the ADR Axis-5 policy (#823).

    DISABLE_AUTOUPDATER set via sessionVariables (Nix owns updates), the
    workspace-CLAUDE.md management option present but empty by default, and
    no home-level skills directory managed.
    """
    cfg = _ci_full_config()
    assert cfg["claudeEnabled"] is True
    assert cfg["autoupdater"] == "1"
    assert cfg["workspaceFiles"] == {}


def test_wave3_full_profile_config() -> None:
    """Wave-3 modules must materialize in the full ci profile (#824)."""
    cfg = _ci_full_config()
    assert cfg["ghdash"] is True
    assert cfg["neovim"] is True
    assert cfg["seshToml"] is True, "sesh.toml must be generated"
    assert cfg["seshSessions"] == [], "sesh sessions must default empty"


@pytest.mark.parametrize("template", ["personal", "python"])
def test_template_is_exposed(template: str) -> None:
    """``templates.<name>`` must point at its starter flake (#827, #930)."""
    info = nix_eval_json(
        f"{REPO_ROOT}#templates.{template}",
        apply='t: { hasPath = t ? path; hasDescription = (t.description or "") != ""; }',
    )
    assert info["hasPath"] and info["hasDescription"]


def test_flake_check_succeeds() -> None:
    """``nix flake check`` evaluates the flake and runs the lightweight checks."""
    result = subprocess.run(
        ["nix", "flake", "check", "--accept-flake-config", str(REPO_ROOT)],
        capture_output=True,
        text=True,
        env=nix_env(),
        timeout=1800,
    )
    assert result.returncode == 0, (
        "nix flake check failed:\n" + result.stdout + "\n" + result.stderr
    )
