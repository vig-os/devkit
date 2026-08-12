"""Downstream flake-stub quality gate (issue #640).

The scaffolded ``assets/workspace/flake.nix`` consumes the shared toolchain as a
flake input (``vigos.url = github:vig-os/devkit``). A change to the vigOS
flake API (e.g. ``lib.mkProjectShell`` or ``overlays.default``) can silently
break a downstream repo's ``direnv allow`` even while this repo's own
``nix flake check`` stays green, because the stub resolves ``vigos`` from the
*published* flake, not the working tree.

This test runs ``nix flake check`` on the stub with the ``vigos`` input
overridden to the local checkout, so the stub is validated against THIS branch.
The CI workflow runs the same check as a direct step; this is the local /
``just test`` parity gate.

The suite is skipped automatically when ``nix`` is not on PATH (mirroring
``test_flake_checks.py``) so it never breaks unrelated lanes.

Refs: #640
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

from .nix_helpers import REPO_ROOT
from .nix_helpers import nix_env as _nix_env

WORKSPACE = REPO_ROOT / "assets" / "workspace"

pytestmark = pytest.mark.skipif(
    shutil.which("nix") is None,
    reason="nix is not installed; flake quality-gate tests require Nix",
)


def test_downstream_flake_stub_checks_against_local_toolchain() -> None:
    """The scaffolded workspace stub evaluates against the local vigOS flake.

    Overriding ``vigos`` to ``path:<repo>`` makes the check validate the stub's
    use of ``lib.mkProjectShell`` / ``overlays.default`` against the toolchain in
    this working tree, catching API drift before it reaches a downstream repo.
    """
    result = subprocess.run(
        [
            "nix",
            "flake",
            "check",
            str(WORKSPACE),
            "--override-input",
            "vigos",
            f"path:{REPO_ROOT}",
            "--accept-flake-config",
        ],
        capture_output=True,
        text=True,
        env=_nix_env(),
        timeout=1800,
    )
    assert result.returncode == 0, (
        "nix flake check on the downstream stub failed:\n"
        + result.stdout
        + "\n"
        + result.stderr
    )
