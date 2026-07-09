"""Capability-module devshell tests (issue #884).

``mkProjectShell`` accepts an opt-in ``modules = [ "<name>" … ]`` string list
(see ``docs/rfcs/ADR-capability-modules.md``). Each shipped module is exposed
as a per-system flake check ``checks.<system>.module-<name>`` (generated from
the ``nix/modules/`` registry), which doubles as the entry point here: these
tests ``nix develop`` the ``native`` module's shell and assert its contract —
the C/C++ toolchain is on the shell's own PATH, generic ``CC``/``CXX`` are
exported, and a trivial setuptools C-extension sdist builds and installs with
``uv`` (the pycatima-class scenario from #639/#879 that motivated the module).

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
