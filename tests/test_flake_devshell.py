"""Dev-shell / image toolchain parity tests for the Nix flake.

These tests are the TDD anchor for the toolchain SSoT (issue #631). The flake
exposes a single ``devTools`` list; this module reads the per-tool *binary
names* straight from the flake (``nix eval .#devShellTools``) so the test can
never drift from the list it is meant to guard.

For every tool in that SSoT it runs ``nix develop -c <bin> <version-flag>`` and
asserts the command exits 0 inside the dev-shell. This guards against
dev-shell / image drift (the ``EXPECTED_VERSIONS`` problem #27 calls out).

The suite is skipped automatically when ``nix`` is not on PATH (e.g. inside the
podman image CI lane) so it never breaks unrelated jobs.

Refs: #631
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# Repository root (two levels up: tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parent.parent

# Whether the host is NixOS. The dev-shell injects the Nix C++ runtime onto
# LD_LIBRARY_PATH only here: NixOS lacks libstdc++ on the default loader path
# (so the pymarkdown wheel needs it, #698) and its system glibc IS the Nix glibc
# (so the injection is ABI-safe). On FHS hosts the system libstdc++ already
# serves the wheel and the injection would leak a newer-glibc runtime into host
# binaries, breaking them with GLIBC_ABI_DT_X86_64_PLT (#703).
IS_NIXOS = Path("/etc/NIXOS").exists()

# Tools whose executable name differs from a plain `<tool> --version` call.
# Default version flag is `--version`; override here when a tool differs.
VERSION_FLAG_OVERRIDES: dict[str, list[str]] = {
    # expect is a Tcl interpreter; it has no --version. `-v` prints the version.
    "expect": ["-v"],
    # tmux uses -V (uppercase) to print its version.
    "tmux": ["-V"],
    # statix has no top-level version flag (`--version` exits 2 with "unexpected
    # argument"); it is a subcommand CLI. `--help` exits 0 and proves the binary
    # is runnable in the dev-shell, which is what this parity check asserts.
    "statix": ["--help"],
    # vig-utils is a subcommand CLI (its `main` requires a subcommand, so
    # `--version` exits 2); `--help` exits 0 and proves the binary runs. The
    # release console scripts it ships (prepare-changelog,
    # renovate-changelog-pr) get their own dedicated PATH test above. Refs #993.
    "vig-utils": ["--help"],
}

pytestmark = pytest.mark.skipif(
    shutil.which("nix") is None,
    reason="nix is not installed; dev-shell parity tests require Nix",
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


@pytest.fixture(scope="session")
def current_system() -> str:
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


@pytest.fixture(scope="session")
def dev_shell_env() -> dict[str, str]:
    """Environment variables exported by the Nix dev-shell.

    Runs ``nix develop -c env`` once and parses the result so the UV-bootstrap
    assertions below share a single (slow) shell instantiation.
    """
    result = subprocess.run(
        ["nix", "develop", str(REPO_ROOT), "-c", "env"],
        capture_output=True,
        text=True,
        env=_nix_env(),
        timeout=900,
    )
    if result.returncode != 0:
        pytest.fail("Failed to capture the dev-shell environment:\n" + result.stderr)
    env: dict[str, str] = {}
    for line in result.stdout.splitlines():
        key, sep, value = line.partition("=")
        if sep:
            env[key] = value
    return env


@pytest.mark.skipif(
    not IS_NIXOS,
    reason=(
        "The Nix C++ runtime is injected onto LD_LIBRARY_PATH only on NixOS; "
        "FHS hosts resolve libstdc++ from the system loader (#703)"
    ),
)
def test_devshell_ld_library_path_provides_libstdcpp(
    dev_shell_env: dict[str, str],
) -> None:
    """On NixOS the dev-shell exposes ``libstdc++.so.6`` on ``LD_LIBRARY_PATH`` (#698).

    The ``pymarkdown`` pre-commit hook runs from pre-commit's own manylinux-wheel
    Python env, whose dependency ``pyjson5`` is a C extension linked against
    ``libstdc++.so.6``. On a NixOS host that library is not on the loader path
    outside an FHS environment, so the hook fails with
    ``ImportError: libstdc++.so.6: cannot open shared object file``. The dev-shell
    therefore exports ``LD_LIBRARY_PATH`` including the Nix C++ runtime so the
    wheel resolves it (the same libstdc++ the Nix toolchain itself links, so no
    version clash with the other dev-shell binaries). The injection is gated to
    NixOS (#703), so this assertion only applies there.
    """
    lib_path = dev_shell_env.get("LD_LIBRARY_PATH", "")
    assert lib_path, "LD_LIBRARY_PATH must be set in the dev-shell"
    roots = [Path(p) for p in lib_path.split(":") if p]
    assert any((root / "libstdc++.so.6").exists() for root in roots), (
        f"libstdc++.so.6 not found under any LD_LIBRARY_PATH entry: {lib_path}"
    )


@pytest.mark.skipif(
    not IS_NIXOS,
    reason=(
        "Exercises the NixOS-only LD_LIBRARY_PATH injection; FHS hosts resolve "
        "libstdc++ from the system loader (#703)"
    ),
)
def test_devshell_pymarkdown_c_extension_imports(dev_shell_env: dict[str, str]) -> None:
    """``pyjson5``'s C extension must load under the dev-shell loader on NixOS (#698).

    Mirrors how the ``pymarkdown`` hook fails: load the manylinux C library with
    the dev-shell's ``LD_LIBRARY_PATH`` in scope. With ``libstdc++`` on the loader
    path the load succeeds; without it it raises the ``libstdc++.so.6``
    ``ImportError`` the hook hit on NixOS. Gated to NixOS, where the injection is
    active (#703).
    """
    lib_path = dev_shell_env.get("LD_LIBRARY_PATH", "")
    assert lib_path, "LD_LIBRARY_PATH must be set in the dev-shell"
    libstdcpp = next(
        (
            p
            for p in (Path(d) / "libstdc++.so.6" for d in lib_path.split(":") if d)
            if p.exists()
        ),
        None,
    )
    assert libstdcpp is not None, (
        f"libstdc++.so.6 not found under LD_LIBRARY_PATH: {lib_path}"
    )
    # ctypes.CDLL exercises the exact dynamic-loader path the C extension uses,
    # without depending on pyjson5 being installed in the project venv.
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import ctypes; ctypes.CDLL({str(libstdcpp)!r}); print('ok')",
        ],
        capture_output=True,
        text=True,
        env={**os.environ, "LD_LIBRARY_PATH": lib_path},
        timeout=120,
    )
    assert proc.returncode == 0 and "ok" in proc.stdout, (
        f"loading libstdc++ via LD_LIBRARY_PATH failed: rc={proc.returncode} "
        f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )


@pytest.mark.skipif(
    IS_NIXOS,
    reason=(
        "On NixOS the system glibc IS the Nix glibc, so injecting the Nix C++ "
        "runtime onto LD_LIBRARY_PATH is ABI-safe and required; this leak guard "
        "only applies to FHS hosts (#703)"
    ),
)
def test_devshell_no_nix_cxx_runtime_leak_on_fhs_host(
    dev_shell_env: dict[str, str],
) -> None:
    """On an FHS host the dev-shell must not put the Nix C++ runtime on ``LD_LIBRARY_PATH`` (#703).

    The Nix ``libstdc++`` is linked against a newer glibc (2.42) than an FHS
    host's system glibc (e.g. Ubuntu 24.04 ships 2.39). Exporting it on
    ``LD_LIBRARY_PATH`` leaks it into host binaries — notably ``/usr/bin/env``,
    which every ``just`` recipe shebang invokes — dragging in the Nix
    ``libm.so.6`` and aborting with ``version 'GLIBC_ABI_DT_X86_64_PLT' not
    found``. FHS hosts already carry ``libstdc++`` on the default loader path, so
    the #698 injection is gated to NixOS; here it must be absent.
    """
    lib_path = dev_shell_env.get("LD_LIBRARY_PATH", "")
    leaked = [
        entry
        for entry in lib_path.split(":")
        if entry.startswith("/nix/store/") and (Path(entry) / "libstdc++.so.6").exists()
    ]
    assert not leaked, (
        "FHS dev-shell must not expose the Nix C++ runtime on LD_LIBRARY_PATH "
        "(it breaks host binaries linked against an older system glibc with "
        f"GLIBC_ABI_DT_X86_64_PLT); leaked entries: {leaked}"
    )


def test_devshell_disables_uv_python_downloads(dev_shell_env: dict[str, str]) -> None:
    """The dev-shell must forbid uv from downloading a managed CPython (#683).

    On a NixOS host a downloaded generic CPython is a dynamically-linked ELF the
    host cannot execute out of the box, so ``uv sync`` (``just init``) aborts.
    ``UV_PYTHON_DOWNLOADS=never`` forces uv to resolve a Nix store interpreter
    instead, mirroring the image path.
    """
    assert dev_shell_env.get("UV_PYTHON_DOWNLOADS") == "never", (
        "UV_PYTHON_DOWNLOADS must be 'never' so uv never fetches a generic "
        f"CPython; got {dev_shell_env.get('UV_PYTHON_DOWNLOADS')!r}"
    )


def test_devshell_uv_python_pins_nix_store_interpreter(
    dev_shell_env: dict[str, str],
) -> None:
    """UV_PYTHON must point at a runnable Nix store CPython 3.14 (#683).

    A store interpreter is patched to the store's loader, so it runs on both
    NixOS and FHS hosts — the cross-host fix for the failed ``uv sync``.
    """
    uv_python = dev_shell_env.get("UV_PYTHON")
    assert uv_python, "UV_PYTHON must be set in the dev-shell"
    assert uv_python.startswith("/nix/store/"), (
        f"UV_PYTHON must be a Nix store interpreter, not {uv_python!r}"
    )
    interpreter = Path(uv_python)
    assert interpreter.is_file() and os.access(interpreter, os.X_OK), (
        f"UV_PYTHON does not point at an executable file: {uv_python}"
    )
    proc = subprocess.run(
        [uv_python, "--version"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0 and "3.14" in proc.stdout, (
        f"UV_PYTHON did not report Python 3.14: rc={proc.returncode} "
        f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )


@pytest.fixture(scope="session")
def dev_shell_tools(current_system: str) -> list[str]:
    """Binary names of every tool in the flake's ``devTools`` SSoT."""
    result = subprocess.run(
        ["nix", "eval", "--json", f"{REPO_ROOT}#devShellTools.{current_system}"],
        capture_output=True,
        text=True,
        env=_nix_env(),
        timeout=900,
    )
    if result.returncode != 0:
        pytest.fail("Failed to read devShellTools from the flake:\n" + result.stderr)
    tools = json.loads(result.stdout)
    assert isinstance(tools, list) and tools, "devShellTools must be a non-empty list"
    return tools


def test_devshell_tools_is_superset_of_agent_toolkit(
    dev_shell_tools: list[str],
) -> None:
    """The SSoT must absorb issue #545's agent-CLI toolkit plus claude."""
    required = {
        "rg",
        "fd",
        "bat",
        "eza",
        "delta",
        "lazygit",
        "zoxide",
        "starship",
        "freeze",
        "expect",
        "nvim",
        "claude",
    }
    missing = required - set(dev_shell_tools)
    assert not missing, f"devTools is missing agent-toolkit tools: {sorted(missing)}"


def test_devshell_provides_bats(dev_shell_tools: list[str]) -> None:
    """The flake must provide BATS so shell tests run without npm (#695).

    The BATS helper libraries (bats-support/-assert/-file) were resolved from
    ``node_modules`` (npm) or the now-removed Debian ``/usr/lib`` path. On the
    Nix toolchain neither exists locally, so the suite must come from the flake
    SSoT: ``bats.withLibraries`` puts ``bats`` on PATH and exports a
    ``BATS_LIB_PATH`` covering the helper libraries.
    """
    assert "bats" in dev_shell_tools, (
        "devTools must provide 'bats' (via bats.withLibraries) so the BATS "
        "suite resolves its helper libraries from the flake, not node_modules"
    )


def test_devshell_provides_precommit_binary_hooks(
    dev_shell_tools: list[str],
) -> None:
    """The flake must provide ruff and typos so their pre-commit hooks run (#697).

    These hooks were sourced from upstream manylinux wheels
    (``astral-sh/ruff-pre-commit``, ``crate-ci/typos``) that a NixOS host cannot
    execute (no FHS ``ld-linux``), forcing ``--no-verify`` on every commit. They
    are now ``language: system`` hooks that resolve their tool from the flake
    dev-shell, so ``ruff`` and ``typos`` must be in the ``devTools`` SSoT.
    """
    required = {"ruff", "typos"}
    missing = required - set(dev_shell_tools)
    assert not missing, (
        "devTools must provide the binary pre-commit tools so their "
        f"language: system hooks resolve from the flake: missing {sorted(missing)}"
    )


def test_devshell_hook_runner_is_prek(dev_shell_tools: list[str]) -> None:
    """The hook runner in the ``devTools`` SSoT must be ``prek``, not ``pre-commit`` (#778).

    Issue #778 migrates the git-hook runner from the Python ``pre-commit`` to the
    Rust ``prek`` (faster, one fewer manylinux/FHS consumer): ``prek`` joins the
    shared ``devTools`` (so it ships in the dev-shell *and* the image), and the
    standalone ``pre-commit`` is dropped from both. Assert the SSoT reflects that
    swap so the dev-shell ↔ image parity holds.
    """
    assert "prek" in dev_shell_tools, (
        "devTools must provide 'prek' as the hook runner (#778)"
    )
    assert "pre-commit" not in dev_shell_tools, (
        "'pre-commit' must be dropped from devTools in favour of 'prek' (#778)"
    )


def test_devshell_bats_lib_path_resolves_helpers(dev_shell_env: dict[str, str]) -> None:
    """BATS_LIB_PATH in the dev-shell must expose the three helper libraries.

    ``bats_load_library bats-support`` (test_helper.bash) only works when
    ``BATS_LIB_PATH`` points at a directory containing the helper libraries.
    The ``bats.withLibraries`` wrapper exports it; assert the libraries are
    actually reachable through it. Refs #695.
    """
    lib_path = dev_shell_env.get("BATS_LIB_PATH", "")
    assert lib_path, "BATS_LIB_PATH must be set in the dev-shell"
    roots = [Path(p) for p in lib_path.split(":") if p]
    for lib in ("bats-support", "bats-assert", "bats-file"):
        assert any((root / lib).is_dir() for root in roots), (
            f"{lib} not found under any BATS_LIB_PATH entry: {lib_path}"
        )


@pytest.mark.parametrize("binary", ["python3"])
def test_devshell_exposes_python3_and_precommit(binary: str) -> None:
    """The dev-shell must put ``python3`` on PATH (#729).

    The image (``imageTools``) ships a Python interpreter (``pythonEnv``), but
    ``mkProjectShell`` carried none: the downstream flake-input / direnv
    dev-shell could reach Python only via ``uv run`` — a dev-shell ↔ image
    parity gap. The hook runner (``prek``, #778) lives in the ``devTools`` SSoT,
    so it is covered by ``devShellTools`` / ``test_each_tool_runs_in_devshell``
    rather than here; only the bare interpreter — intentionally *not* in
    ``devTools`` (it would collide with the image's ``pythonEnv``) — is asserted
    explicitly.

    The check runs under ``nix develop --ignore-environment`` so it asserts the
    dev-shell's *own* PATH contribution and is not satisfied by a host
    ``python3`` leaking through the inherited environment (the exact way the gap
    hid until #729).
    """
    cmd = [
        "nix",
        "develop",
        "--ignore-environment",
        "--keep",
        "HOME",
        str(REPO_ROOT),
        "-c",
        "bash",
        "-c",
        f"command -v {binary}",
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=_nix_env(),
        timeout=900,
    )
    # `command -v` exits 0 iff the binary is on PATH; rely on the exit code
    # (the shellHook's banner pollutes stdout, so it is not a presence signal).
    assert proc.returncode == 0, (
        f"{binary} must be on the dev-shell's own PATH (#729): "
        f"rc={proc.returncode} stdout={proc.stdout.strip()!r} "
        f"stderr={proc.stderr.strip()[:200]}"
    )


@pytest.mark.parametrize("script", ["prepare-changelog", "renovate-changelog-pr"])
def test_devshell_exposes_vig_utils_console_scripts(script: str) -> None:
    """The dev-shell must expose vig-utils' release console scripts on PATH (#993).

    ``prepare-changelog`` and ``renovate-changelog-pr`` are console scripts of
    ``packages/vig-utils``. They are baked into the image's Python env
    (``pythonEnv``) but were historically absent from the ``devTools`` SSoT, so a
    consumer ``mkProjectShell`` dev-shell (direnv mode) lacked them — blocking
    the mode-aware release workflows (#991) for the container-less modes. Adding
    ``vig-utils`` to ``devTools`` delivers the scripts to the dev-shell as well.

    The check runs under ``nix develop --ignore-environment`` so it asserts the
    dev-shell's *own* PATH contribution and is not satisfied by a host script
    leaking through the inherited environment.
    """
    cmd = [
        "nix",
        "develop",
        "--ignore-environment",
        "--keep",
        "HOME",
        str(REPO_ROOT),
        "-c",
        "bash",
        "-c",
        f"command -v {script}",
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=_nix_env(),
        timeout=900,
    )
    assert proc.returncode == 0, (
        f"{script} must be on the dev-shell's own PATH (#993): "
        f"rc={proc.returncode} stdout={proc.stdout.strip()!r} "
        f"stderr={proc.stderr.strip()[:200]}"
    )


def test_each_tool_runs_in_devshell(dev_shell_tools: list[str]) -> None:
    """Every tool in ``devTools`` is runnable inside ``nix develop``."""
    failures: list[str] = []
    for tool in dev_shell_tools:
        flag = VERSION_FLAG_OVERRIDES.get(tool, ["--version"])
        cmd = ["nix", "develop", str(REPO_ROOT), "-c", tool, *flag]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=_nix_env(),
            timeout=900,
        )
        if proc.returncode != 0:
            failures.append(
                f"{tool} ({' '.join(flag)}) exited {proc.returncode}: "
                f"{proc.stderr.strip()[:200]}"
            )
    assert not failures, "Tools failed inside nix develop:\n" + "\n".join(failures)


# ---------------------------------------------------------------------------
# Overridable Python interpreter (#1038) — `mkProjectShell` accepts an opt-in
# `python ? pkgs.python314` argument so a consumer whose nixpkgs C-extension
# dependency is built against a different CPython ABI (e.g. `pkgs.freecad`,
# built against the nixpkgs default Python 3.13) can align the interpreter uv
# pins. The default stays byte-identical to the pinned-3.14 builder.
# ---------------------------------------------------------------------------


def _mkprojectshell_expr(system: str, args: str) -> str:
    """A Nix expression building ``flake.lib.mkProjectShell`` with ``args``.

    Mirrors the ``test_flake_modules`` / ``test_flake_hooks`` idiom: import the
    pinned nixpkgs with the flake's overlay so ``pkgs`` matches the flake's own
    dev-shell, then apply ``mkProjectShell``. ``--impure`` is required for the
    ``builtins.getFlake`` on the local path.
    """
    return f"""
    let
      flake = builtins.getFlake "path:{REPO_ROOT}";
      system = "{system}";
      pkgs = import flake.inputs.nixpkgs {{
        inherit system;
        overlays = [ flake.overlays.default ];
        config.allowUnfree = true;
      }};
    in flake.lib.mkProjectShell {{ inherit pkgs; {args} }}
    """


def test_devshell_python_default_is_byte_identical(current_system: str) -> None:
    """Passing the explicit default ``python`` is byte-identical to no argument (#1038).

    The parity guard for the new argument (same pattern as the ``modules`` /
    ``hooks`` opt-ins): building ``mkProjectShell { python = pkgs.python314; }``
    must produce the exact same derivation as the flake's own default dev-shell,
    so adding the knob cannot silently change the pinned-3.14 shell.
    """
    expr = f"""
    let
      flake = builtins.getFlake "path:{REPO_ROOT}";
      system = "{current_system}";
      pkgs = import flake.inputs.nixpkgs {{
        inherit system;
        overlays = [ flake.overlays.default ];
        config.allowUnfree = true;
      }};
    in {{
      default = flake.devShells.${{system}}.default.drvPath;
      explicitDefault =
        (flake.lib.mkProjectShell {{ inherit pkgs; python = pkgs.python314; }}).drvPath;
    }}
    """
    result = subprocess.run(
        ["nix", "eval", "--impure", "--json", "--expr", expr],
        capture_output=True,
        text=True,
        env=_nix_env(),
        timeout=300,
    )
    assert result.returncode == 0, result.stderr
    paths = json.loads(result.stdout)
    assert paths["default"] == paths["explicitDefault"], (
        "explicit python=python314 must match the default dev-shell drv byte-for-byte; "
        f"got {paths!r}"
    )


def test_devshell_python_override_switches_interpreter(current_system: str) -> None:
    """``python = pkgs.python313`` makes UV_PYTHON and ``python3`` follow it (#1038).

    The ABI-alignment knob for nixpkgs C-extension deps (freecad-class): the
    overridden interpreter must be the one uv pins (``UV_PYTHON``) and the one on
    the shell's own PATH (``python3``). Exercised with 3.13 (the nixpkgs default,
    reliably cached) rather than building/pulling FreeCAD, which is far too heavy
    for CI — the FreeCAD acceptance case is covered by the cad2gdml onboarding
    spike (#1040 Phase 0), not here.
    """
    expr = _mkprojectshell_expr(current_system, "python = pkgs.python313;")
    script = 'printf "\\nUV_PYTHON=%s\\n" "$UV_PYTHON"; python3 --version'
    proc = subprocess.run(
        [
            "nix",
            "develop",
            "--impure",
            "--ignore-environment",
            "--keep",
            "HOME",
            "--expr",
            expr,
            "-c",
            "bash",
            "-c",
            script,
        ],
        capture_output=True,
        text=True,
        env=_nix_env(),
        timeout=1800,
    )
    assert proc.returncode == 0, (
        f"failed to build/enter the python=python313 dev-shell: {proc.stderr[-500:]}"
    )
    lines = proc.stdout.splitlines()
    uv_python = next(
        (ln.partition("=")[2] for ln in lines if ln.startswith("UV_PYTHON=")), ""
    )
    assert uv_python.startswith("/nix/store/") and uv_python.endswith("python3.13"), (
        f"UV_PYTHON must follow the override to a store python3.13; got {uv_python!r}"
    )
    version_line = lines[-1] if lines else ""
    assert "3.13" in version_line, (
        f"python3 on the shell PATH must report 3.13 under the override; got {version_line!r} "
        f"(full stdout: {proc.stdout!r})"
    )
