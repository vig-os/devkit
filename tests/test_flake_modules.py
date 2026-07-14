"""Capability-module devshell tests (issue #884).

``mkProjectShell`` accepts an opt-in ``modules = [ "<name>" … ]`` string list
(see ``docs/rfcs/ADR-capability-modules.md``). Each shipped module is exposed
as a per-system flake check ``checks.<system>.module-<name>`` (generated from
the ``nix/modules/`` registry), which doubles as the entry point here: these
tests ``nix develop`` a module's shell and assert its contract. For ``native``
(#884): the C/C++ toolchain is on the shell's own PATH, generic ``CC``/``CXX``
are exported, and a trivial setuptools C-extension sdist builds and installs
with ``uv`` (the pycatima-class scenario from #639/#879). For ``node`` (#1027):
``node`` + bundled ``npm`` resolve, and the ``{ name = "node"; version = …; }``
per-module-options form pins the Node major (the mechanism the ADR deferred).

The zero-module parity guarantee (the default dev-shell is byte-identical to
the pre-module builder) is covered by ``tests/test_flake_devshell.py`` staying
green unchanged, not here.

The suite is skipped automatically when ``nix`` is not on PATH (mirroring the
other flake test modules) so it never breaks unrelated lanes.

Refs: #884
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

# Repository root (two levels up: tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "native_ext"

pytestmark = pytest.mark.skipif(
    shutil.which("nix") is None,
    reason="nix is not installed; capability-module tests require Nix",
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


def _develop_native(
    current_system: str, script: str, *, pure: bool = True, timeout: int = 1800
) -> subprocess.CompletedProcess[str]:
    """Run a bash script inside the ``native`` module's devshell.

    With ``pure=True`` (default) it uses ``--ignore-environment`` (keeping only
    HOME) so assertions exercise the shell's *own* PATH/env contribution and
    cannot be satisfied by a host toolchain leaking through the inherited
    environment — the same guard ``test_devshell_exposes_python3_and_precommit``
    uses (#729). ``pure=False`` keeps the ambient environment for steps that
    need the host's network/TLS configuration (e.g. uv fetching a build
    backend from PyPI).
    """
    isolation = ["--ignore-environment", "--keep", "HOME"] if pure else []
    return subprocess.run(
        [
            "nix",
            "develop",
            *isolation,
            f"{REPO_ROOT}#checks.{current_system}.module-native",
            "-c",
            "bash",
            "-c",
            script,
        ],
        capture_output=True,
        text=True,
        env=_nix_env(),
        timeout=timeout,
    )


def test_native_module_provides_build_toolchain(current_system: str) -> None:
    """The ``native`` module puts the sdist-building toolchain on PATH (#884).

    ``stdenv.cc`` (cc/c++), ``cmake``, ``gnumake`` and ``pkg-config`` are the
    curated definition of the generic native-build capability — what
    scikit-build-core / setuptools / meson-python sdist builds actually invoke.
    """
    proc = _develop_native(
        current_system,
        "for bin in cc c++ cmake make pkg-config; do command -v $bin; done",
    )
    assert proc.returncode == 0, (
        "native-module devshell is missing toolchain binaries: "
        f"rc={proc.returncode} stdout={proc.stdout.strip()!r} "
        f"stderr={proc.stderr.strip()[:300]}"
    )


def test_native_module_exports_generic_cc_cxx(current_system: str) -> None:
    """The ``native`` module exports ``CC=cc`` / ``CXX=c++`` (#884).

    Generic POSIX names, not store paths: build backends that consult the
    environment resolve them via the module-provided PATH, matching the
    image-side sysconfig sanitize (#879/#893) which rewrote the baked
    interpreter's compiler records to the same generic names.
    """
    proc = _develop_native(current_system, 'printf "\\n%s:%s" "$CC" "$CXX"')
    assert proc.returncode == 0, (
        f"failed to read CC/CXX from the native-module devshell: {proc.stderr[:300]}"
    )
    # The default shellHook banner writes to stdout, so only the last line is
    # the probe's answer.
    got = proc.stdout.splitlines()[-1] if proc.stdout else ""
    assert got == "cc:c++", f"native module must export CC=cc and CXX=c++; got {got!r}"


def test_native_module_builds_c_extension_sdist_with_uv(
    current_system: str, tmp_path: Path
) -> None:
    """A trivial C-extension sdist builds and installs with uv in the shell (#884).

    End-to-end acceptance for the module: package the fixture as an sdist
    (``uv build --sdist``), then compile-install it into a fresh venv
    (``uv pip install <sdist>``) and import it — exactly the path ``uv sync``
    takes for a dependency with no ``cp314`` wheel (pycatima-class, #639/#879).
    The devshell pins ``UV_PYTHON`` to the store CPython and forbids managed
    downloads, so the compile runs against the same interpreter the consumer
    contract prescribes.
    """
    project = tmp_path / "native-ext"
    shutil.copytree(FIXTURE, project)
    script = (
        "set -euo pipefail\n"
        f"cd {project}\n"
        "uv build --sdist --out-dir dist\n"
        "uv venv .venv\n"
        "uv pip install --python .venv/bin/python dist/native_ext-0.1.0.tar.gz\n"
        '.venv/bin/python -c "import native_ext; '
        "assert native_ext.answer() == 42; print('sdist-ok')\"\n"
    )
    proc = _develop_native(current_system, script, pure=False)
    assert proc.returncode == 0 and "sdist-ok" in proc.stdout, (
        "uv sdist build/install failed inside the native-module devshell: "
        f"rc={proc.returncode}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr[-2000:]}"
    )


# ---------------------------------------------------------------------------
# node module (#1027) — the Node/TypeScript capability. v1 contract (packages
# only): `nodejs` (which bundles npm) in the dev-shell, with a selectable major
# version via the ADR's per-module-options migration path — a `modules` entry
# may be `{ name = "node"; version = 22; }` (attrset) alongside the plain
# `"node"` string (nixpkgs default). See docs/rfcs/ADR-capability-modules.md.
# ---------------------------------------------------------------------------


def _develop_module(
    current_system: str, module: str, script: str, *, timeout: int = 1800
) -> subprocess.CompletedProcess[str]:
    """Run a bash script inside the generated ``module-<module>`` devshell.

    Purity guard (``--ignore-environment``, keeping only HOME) as in
    ``_develop_native``: the assertions must exercise the module's OWN PATH
    contribution and never be satisfied by a host toolchain leaking through.
    """
    return subprocess.run(
        [
            "nix",
            "develop",
            "--ignore-environment",
            "--keep",
            "HOME",
            f"{REPO_ROOT}#checks.{current_system}.module-{module}",
            "-c",
            "bash",
            "-c",
            script,
        ],
        capture_output=True,
        text=True,
        env=_nix_env(),
        timeout=timeout,
    )


def _develop_expr(
    expr: str, script: str, *, timeout: int = 1800
) -> subprocess.CompletedProcess[str]:
    """Run a bash script inside an ad-hoc devshell built from a Nix expression.

    Used for the versioned module form, which the registry-generated
    ``module-node`` check (plain-string default) cannot express: it builds
    ``flake.lib.mkProjectShell`` directly with an attrset ``modules`` entry.
    ``--impure`` is required for ``builtins.getFlake`` on the local path.
    """
    return subprocess.run(
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
        timeout=timeout,
    )


def test_node_module_provides_node_and_npm(current_system: str) -> None:
    """The ``node`` module puts ``node`` and its bundled ``npm`` on PATH (#1027).

    The plain-string ``modules = [ "node" ]`` form (exercised through the
    registry-generated ``module-node`` check) contributes the nixpkgs-default
    ``nodejs``, which bundles ``npm`` — both must resolve from the shell's own
    PATH, not the host's.
    """
    proc = _develop_module(
        current_system,
        "node",
        "command -v node && command -v npm && node --version && npm --version",
    )
    assert proc.returncode == 0, (
        "node-module devshell is missing node/npm: "
        f"rc={proc.returncode} stdout={proc.stdout.strip()!r} "
        f"stderr={proc.stderr.strip()[:300]}"
    )


def test_node_module_version_option_pins_major(current_system: str) -> None:
    """``{ name = "node"; version = 22; }`` selects ``pkgs.nodejs_22`` (#1027).

    The per-module-options migration path the ADR deferred: an attrset entry
    carries a ``version`` that maps to ``pkgs.nodejs_<major>``. Build that shell
    directly (the registry check only covers the default form) and assert the
    running interpreter is the pinned major.

    A maintained LTS major (22) is used deliberately: the pinned nixpkgs marks
    EOL majors (e.g. nodejs_20) insecure, so pinning one throws unless the
    consumer opts into ``permittedInsecurePackages`` — a nixpkgs policy the
    module surfaces rather than masks (documented in docs/NIX.md).
    """
    expr = f"""
    let
      flake = builtins.getFlake "path:{REPO_ROOT}";
      system = builtins.currentSystem;
      pkgs = import flake.inputs.nixpkgs {{
        inherit system;
        overlays = [ flake.overlays.default ];
        config.allowUnfree = true;
      }};
    in flake.lib.mkProjectShell {{
      inherit pkgs;
      modules = [ {{ name = "node"; version = 22; }} ];
    }}
    """
    proc = _develop_expr(expr, "node --version")
    assert proc.returncode == 0, (
        f"failed to build/enter the versioned node devshell: {proc.stderr[-500:]}"
    )
    got = proc.stdout.strip().splitlines()[-1] if proc.stdout else ""
    assert got.startswith("v22."), (
        f"node module version=22 must run Node 22.x; got {got!r}"
    )


def test_node_module_rejects_unknown_option(current_system: str) -> None:
    """An unrecognized module option fails at eval time with a clear message (#1027).

    The options mechanism is intentionally strict: only keys the module declares
    are accepted, so a mistyped or unsupported knob (here ``channel``) is a hard
    eval error, never a silently-ignored no-op.
    """
    expr = f"""
    let
      flake = builtins.getFlake "path:{REPO_ROOT}";
      system = builtins.currentSystem;
      pkgs = import flake.inputs.nixpkgs {{
        inherit system;
        overlays = [ flake.overlays.default ];
        config.allowUnfree = true;
      }};
    in (flake.lib.mkProjectShell {{
      inherit pkgs;
      modules = [ {{ name = "node"; channel = 20; }} ];
    }}).drvPath
    """
    result = subprocess.run(
        ["nix", "eval", "--impure", "--expr", expr],
        capture_output=True,
        text=True,
        env=_nix_env(),
        timeout=300,
    )
    assert result.returncode != 0, "unknown node option must fail eval, not pass"
    assert "channel" in result.stderr and "node" in result.stderr, (
        f"error must name the offending option and module; got: {result.stderr[-500:]}"
    )
