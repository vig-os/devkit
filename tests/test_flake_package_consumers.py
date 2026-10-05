"""Consuming a devkit project's ``packages`` from another flake (#1832).

A scaffolded project's flake has ``vigos`` as an input, so a downstream flake
that takes the project as an input to get one binary inherits devkit's whole
input tree in its lock. ``docs/MIGRATION.md`` gives the downstream a stanza
that builds the package with the downstream's own nixpkgs and drops every
devkit input a package build never reads.

That stanza is a CONTRACT devkit has to keep: if a package build ever starts
reading one of the dropped inputs, every consumer using it breaks. So the test
executes the documented block itself, against a Rust project rendered from the
``#rust`` template and the seeded ``mkRustProject`` flake, with ``vigos``
pointed at this checkout. The doc is what is tested; there is no second copy.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from typing import TYPE_CHECKING

import pytest

from .nix_helpers import REPO_ROOT, current_system
from .nix_helpers import nix_env as _nix_env

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.skipif(
    shutil.which("nix") is None, reason="nix is required to build the flakes"
)

MIGRATION = REPO_ROOT / "docs" / "MIGRATION.md"
# The devkit inputs a package build actually reads. Everything else is the dev
# shell, the home-manager modules, the hook generator and the services stack.
PACKAGE_INPUTS = {"nixpkgs", "flake-utils", "crane", "fenix"}


def _documented_stanza() -> str:
    """The downstream ``flake.nix`` block from MIGRATION.md."""
    blocks = re.findall(r"```nix\n(.*?)```", MIGRATION.read_text(), re.DOTALL)
    matches = [b for b in blocks if "my-tool.inputs.vigos.inputs.nixpkgs.follows" in b]
    assert len(matches) == 1, (
        "expected exactly one documented package-consumer stanza in MIGRATION.md"
    )
    return matches[0]


def _devkit_inputs() -> set[str]:
    result = subprocess.run(
        [
            "nix",
            "eval",
            "--impure",
            "--json",
            "--expr",
            f'builtins.attrNames (builtins.getFlake "path:{REPO_ROOT}").inputs',
        ],
        capture_output=True,
        text=True,
        env=_nix_env(),
        timeout=300,
    )
    assert result.returncode == 0, result.stderr[-1500:]
    return set(json.loads(result.stdout))


def test_stanza_drops_exactly_the_inputs_a_package_never_reads() -> None:
    """The documented drop list tracks devkit's inputs (#1832).

    A new devkit input that packages do not need must be added to the stanza,
    or consumers silently start carrying it again. One that packages DO need
    belongs in PACKAGE_INPUTS, and the build test below proves the claim.
    """
    dropped = set(
        re.findall(
            r'my-tool\.inputs\.vigos\.inputs\.([\w-]+)\.follows = "";',
            _documented_stanza(),
        )
    )
    assert dropped == _devkit_inputs() - PACKAGE_INPUTS


def _git_tree(path: Path) -> None:
    """Make ``path`` a committed git tree: a flake's source is its git index."""
    git = [
        "git",
        "-C",
        str(path),
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.com",
    ]
    subprocess.run([*git[:3], "init", "-q"], check=True)
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run(
        [
            *git,
            "-c",
            "commit.gpgsign=false",
            "-c",
            "core.hooksPath=/dev/null",
            "commit",
            "-q",
            "-m",
            "init",
        ],
        check=True,
    )


def test_documented_stanza_builds_a_rust_projects_package(tmp_path: Path) -> None:
    """The stanza, verbatim, builds a seeded Rust project's package (#1832)."""
    project = tmp_path / "my-tool"
    shutil.copytree(REPO_ROOT / "templates" / "rust", project)
    shutil.copy(
        REPO_ROOT / "assets" / "flake.d" / "rust.flake.nix", project / "flake.nix"
    )
    _git_tree(project)

    nixpkgs_rev = json.loads((REPO_ROOT / "flake.lock").read_text())["nodes"][
        "nixpkgs"
    ]["locked"]["rev"]
    downstream = tmp_path / "downstream"
    downstream.mkdir()
    flake = (
        _documented_stanza()
        .replace("github:my-org/my-tool", f"git+file://{project}")
        # Devkit's own pin, so the build hits the cache instead of a fresh
        # nixpkgs; the stanza's point is that it is THIS flake's choice.
        .replace(
            "github:NixOS/nixpkgs/nixos-26.05", f"github:NixOS/nixpkgs/{nixpkgs_rev}"
        )
        .replace("x86_64-linux", current_system())
    )
    (downstream / "flake.nix").write_text(flake)
    _git_tree(downstream)

    result = subprocess.run(
        [
            "nix",
            "build",
            "--no-link",
            "--no-write-lock-file",
            f"{downstream}#default",
            "--override-input",
            "my-tool/vigos",
            f"path:{REPO_ROOT}",
        ],
        capture_output=True,
        text=True,
        env=_nix_env(),
        timeout=1800,
    )
    assert result.returncode == 0, (
        "the documented package-consumer stanza no longer builds; a package "
        "build now reads one of the inputs it drops:\n" + result.stderr[-3000:]
    )
