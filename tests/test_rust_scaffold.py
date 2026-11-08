"""The Rust pack's entry points: the seeded flake and the ``#rust`` template (#1496).

``assets/flake.d/rust.flake.nix`` replaces the scaffold's ``flake.nix`` on a
fresh direnv scaffold of a Rust repo. It is a second copy of the stub, so the
parts both copies must agree on are pinned here: the ``.vig-os`` reader block
(managed, "leave it") and the consumer-owned ``extraPackages`` block. If they
drift, a Rust repo's hooks would read the manifest differently from every other
repo's.

``templates/rust`` is the ``nix flake init -t #rust`` starter. It is built
through ``mkRustProject`` with its full check suite, so a template that is not
fmt/clippy clean, or whose lockfile does not match its manifest, fails here
rather than in an adopter's first ``nix flake check``.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from .nix_helpers import REPO_ROOT
from .nix_helpers import nix_env as _nix_env

BASE_FLAKE = REPO_ROOT / "assets" / "workspace" / "flake.nix"
RUST_FLAKE = REPO_ROOT / "assets" / "flake.d" / "rust.flake.nix"
TEMPLATE = REPO_ROOT / "templates" / "rust"

# The managed `.vig-os` reader: from its comment header to the last knob.
_MANAGED_BLOCK = re.compile(
    r"^ *# Devkit knobs read from \.vig-os.*?"
    r'refsOptionalTypes = vigOsList "DEVKIT_REFS_OPTIONAL_TYPES";\n',
    re.DOTALL | re.MULTILINE,
)
# The consumer-owned tool list, header comment included.
_EXTRA_PACKAGES_BLOCK = re.compile(
    r"^ *# ─+\n *# Your project tools go here\..*?^ *\];\n",
    re.DOTALL | re.MULTILINE,
)
# The commented hooks opt-in block (#1167's inserted comment refers to it).
_HOOKS_BLOCK = re.compile(
    r"^ *# Opt-in: let the flake GENERATE.*?hooksExcludes = \[.*?\n",
    re.DOTALL | re.MULTILINE,
)
# init-workspace.sh's activate_flake_hooks_default anchors on this exact line.
_HOOKS_ANCHOR = "            extraPackages = extraPackages pkgs;\n"
_KNOBS = ("workflow", "branchTypes", "commitTypes", "refsPolicy", "refsOptionalTypes")


def _block(pattern: re.Pattern[str], text: str, where: str) -> str:
    match = pattern.search(text)
    assert match, f"block not found in {where}"
    return match.group(0)


class TestRustFlakeLockstep:
    """The Rust flake agrees with the base stub where they must (#1496, #1810)."""

    def test_managed_vig_os_reader_is_identical(self) -> None:
        base, rust = BASE_FLAKE.read_text(), RUST_FLAKE.read_text()
        assert _block(_MANAGED_BLOCK, rust, "rust.flake.nix") == _block(
            _MANAGED_BLOCK, base, "flake.nix"
        ), (
            "the .vig-os reader in assets/flake.d/rust.flake.nix has drifted from "
            "assets/workspace/flake.nix; copy the base block over verbatim"
        )

    def test_extra_packages_block_is_identical(self) -> None:
        base, rust = BASE_FLAKE.read_text(), RUST_FLAKE.read_text()
        assert _block(_EXTRA_PACKAGES_BLOCK, rust, "rust.flake.nix") == _block(
            _EXTRA_PACKAGES_BLOCK, base, "flake.nix"
        )

    def test_hooks_opt_in_block_is_identical(self) -> None:
        """activate_flake_hooks_default's comment says "like the opt-in block below"."""
        base, rust = BASE_FLAKE.read_text(), RUST_FLAKE.read_text()
        assert _block(_HOOKS_BLOCK, rust, "rust.flake.nix") == _block(
            _HOOKS_BLOCK, base, "flake.nix"
        )

    def test_carries_the_flake_hooks_anchor_exactly_once(self) -> None:
        """activate_flake_hooks_default (#1167) inserts `hooks = { };` after it."""
        assert RUST_FLAKE.read_text().count(_HOOKS_ANCHOR) == 1

    def test_forwards_every_knob_behind_a_function_args_probe(self) -> None:
        """Each knob reaches mkRustProject, guarded for a floating vigos (#1249, #1810)."""
        rust = RUST_FLAKE.read_text()
        for knob in _KNOBS:
            assert f"builtins.functionArgs vigos.lib.mkRustProject ? {knob}" in rust, (
                f"rust.flake.nix does not forward `{knob}` behind a probe"
            )
            assert f"inherit {knob};" in rust

    def test_assigns_checks_and_packages_statix_clean(self) -> None:
        """`inherit (rust) checks packages;`, not two assignments (statix [04], #1810)."""
        rust = RUST_FLAKE.read_text()
        assert "inherit (rust) checks packages;" in rust
        assert "checks = rust.checks" not in rust


def _nix(*args: str, timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["nix", *args],
        capture_output=True,
        text=True,
        env=_nix_env(),
        timeout=timeout,
    )


requires_nix = pytest.mark.skipif(
    shutil.which("nix") is None, reason="nix is required to evaluate the flake"
)


@requires_nix
class TestRustTemplate:
    """``nix flake init -t #rust`` ships a crate the pack accepts as-is (#1496)."""

    def test_template_is_exported(self) -> None:
        result = _nix(
            "eval",
            "--json",
            f"path:{REPO_ROOT}#templates.rust",
            "--apply",
            "t: { inherit (t) description; files = builtins.attrNames "
            "(builtins.readDir t.path); }",
        )
        assert result.returncode == 0, result.stderr[-1500:]
        template = json.loads(result.stdout)
        assert "Rust" in template["description"]
        for name in ("Cargo.toml", "Cargo.lock", "src", "README.md"):
            assert name in template["files"], f"templates/rust lacks {name}"

    def test_template_passes_the_full_check_suite(self) -> None:
        """Every ``mkRustProject`` check builds green on the template crate.

        fmt, clippy (warnings denied), nextest, doctest, doc and the package
        build itself. Built, not evaluated: a template that only evaluates can
        still hand an adopter a red first ``nix flake check``.
        """
        expr = f"""
        let
          flake = builtins.getFlake "path:{REPO_ROOT}";
          pkgs = import flake.inputs.nixpkgs {{
            system = builtins.currentSystem;
            overlays = [ flake.overlays.default ];
          }};
          rust = flake.lib.mkRustProject {{
            inherit pkgs;
            src = {TEMPLATE};
          }};
        in
        pkgs.linkFarmFromDrvs "rust-template-checks" (builtins.attrValues rust.checks)
        """
        result = _nix("build", "--impure", "--no-link", "--expr", expr)
        assert result.returncode == 0, result.stderr[-3000:]


def _github_slug(heading: str) -> str:
    """GitHub's heading anchor: lowercase, punctuation dropped, spaces to dashes."""
    slug = re.sub(r"[^\w\- ]", "", heading.strip().lower())
    return slug.replace(" ", "-")


def test_bypass_notice_links_to_a_real_migration_heading() -> None:
    """init-workspace.sh's Rust-pack notice points at an existing section (#1831)."""
    script = (REPO_ROOT / "assets" / "init-workspace.sh").read_text()
    anchors = set(re.findall(r"docs/MIGRATION\.md#([\w-]+)", script))
    assert "rust-projects-the-rust-pack" in anchors
    headings = {
        _github_slug(line.lstrip("#"))
        for line in (REPO_ROOT / "docs" / "MIGRATION.md").read_text().splitlines()
        if line.startswith("#")
    }
    missing = anchors - headings
    assert not missing, (
        f"init-workspace.sh links to missing MIGRATION.md anchors: {missing}"
    )
