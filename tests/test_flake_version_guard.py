"""Shell-entry version-skew guard tests for ``mkProjectShell`` (#1263).

A direnv consumer's ``.vig-os`` ``DEVKIT_VERSION`` (advanced by the scaffold
upgrade) and its ``vigos`` flake input (frozen by ``flake.lock``) deliver
coupled halves of the same release. A floating input silently lags: the lock
stays wherever the last ``nix flake update vigos`` saw it, so the dev shell
runs last release's toolchain against this release's scaffold (#1263 — the
1.4.0 ``setup-labels`` planning label deletion under a 1.4.1 scaffold).

``mkProjectShell`` therefore bakes its own release version (read at eval time
from the devkit repo's ``.vig-os``, i.e. the locked input rev) into the
shellHook and compares it against the workspace ``.vig-os`` on every shell
entry, warning on a mismatch. These tests enter the devkit's own dev shell
(``devShells.default`` is a plain ``mkProjectShell`` instantiation) from a
synthetic workspace directory and assert the warning fires — and stays silent —
in the right cases.

The suite is skipped when ``nix`` is not on PATH, like the other flake suites.

Refs: #1263
"""

from __future__ import annotations

import re
import shutil
import subprocess
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from .nix_helpers import REPO_ROOT
from .nix_helpers import nix_env as _nix_env

# The stable marker the guard prints; keep in sync with flake.nix.
WARNING_MARKER = "dev-shell toolchain is devkit"
REMEDY_MARKER = "nix flake update vigos"

pytestmark = pytest.mark.skipif(
    shutil.which("nix") is None,
    reason="nix is not installed; dev-shell guard tests require Nix",
)


def _devkit_version() -> str:
    """The devkit's own release version, from the repo-root ``.vig-os``."""
    manifest = (REPO_ROOT / ".vig-os").read_text()
    match = re.search(r"^DEVKIT_VERSION=(.+)$", manifest, flags=re.MULTILINE)
    assert match, "repo-root .vig-os must carry DEVKIT_VERSION"
    return match.group(1).strip()


def _enter_shell(workspace: Path) -> str:
    """Enter the devkit dev shell from ``workspace`` and return its stderr."""
    result = subprocess.run(
        ["nix", "develop", str(REPO_ROOT), "-c", "bash", "-c", ":"],
        capture_output=True,
        text=True,
        env=_nix_env(),
        cwd=workspace,
        timeout=900,
    )
    assert result.returncode == 0, (
        f"nix develop failed from {workspace}:\n{result.stderr}"
    )
    return result.stderr


def test_warns_when_workspace_pin_differs(tmp_path: Path) -> None:
    """A workspace pinned to a different final release gets the skew warning."""
    (tmp_path / ".vig-os").write_text("DEVKIT_VERSION=0.0.1\nDEVKIT_MODE=direnv\n")
    stderr = _enter_shell(tmp_path)
    assert WARNING_MARKER in stderr
    assert _devkit_version() in stderr
    assert "DEVKIT_VERSION=0.0.1" in stderr
    assert REMEDY_MARKER in stderr


def test_silent_when_workspace_pin_matches(tmp_path: Path) -> None:
    """A workspace pinned to the shell's own release stays silent."""
    (tmp_path / ".vig-os").write_text(
        f"DEVKIT_VERSION={_devkit_version()}\nDEVKIT_MODE=direnv\n"
    )
    stderr = _enter_shell(tmp_path)
    assert WARNING_MARKER not in stderr


def test_silent_on_prerelease_pin(tmp_path: Path) -> None:
    """An ``-rc`` pin never warns: release-train lanes deliberately bump to rc
    tags the floating input cannot follow (rc content lives on the release
    branch, not the default branch a ``nix flake update vigos`` fetches)."""
    (tmp_path / ".vig-os").write_text("DEVKIT_VERSION=99.0.0-rc1\n")
    stderr = _enter_shell(tmp_path)
    assert WARNING_MARKER not in stderr


def test_silent_without_manifest(tmp_path: Path) -> None:
    """A bare ``mkProjectShell`` consumer (no ``.vig-os``) is left alone."""
    stderr = _enter_shell(tmp_path)
    assert WARNING_MARKER not in stderr
