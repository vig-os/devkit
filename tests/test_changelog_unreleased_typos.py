"""Tests for scripts/check_unreleased_typos.py — the Unreleased typo gate (#1534).

The gate exists because a released changelog entry is immutable *and* synced into
every devcontainer-mode consumer's worktree
(``assets/workspace/.devcontainer/CHANGELOG.md``), where the consumer's own
``.typos.toml`` — seeded once, never overwritten — has to lint it. Catching such
a token after the release is useless, so the hook lints the ``## Unreleased``
section with **no allowlist** (``typos --isolated``) before the text can ever be
committed. Released sections keep their allowlisted tokens and must never fail.

Refs: #1534
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

scripts_dir = Path(__file__).parent.parent / "scripts"
project_root = scripts_dir.parent

pytestmark = pytest.mark.skipif(
    shutil.which("typos") is None,
    reason="typos is not on PATH; the Unreleased gate shells out to it",
)


def _load_checker():
    spec = importlib.util.spec_from_file_location(
        "check_unreleased_typos", scripts_dir / "check_unreleased_typos.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_unreleased_typos"] = module
    spec.loader.exec_module(module)
    return module


# A token devkit's own .typos.toml allows (#1488's `mis`) but `typos --isolated`
# flags — i.e. exactly the class of text this gate exists to keep out of a
# release: green here, red in a consumer whose seed predates the entry.
SEED_DEPENDENT = "mis-parses"

HEADER = """# Changelog

All notable changes to this project will be documented in this file.

"""

RELEASED_SECTION = """## [1.10.0] - 2026-08-14

### Fixed

- **Something released**
  - the old code had two latent {token} in it
"""


def _changelog(tmp_path: Path, unreleased: str, released: str = "") -> Path:
    path = tmp_path / "CHANGELOG.md"
    path.write_text(
        f"{HEADER}## Unreleased\n\n{unreleased}\n{released}", encoding="utf-8"
    )
    return path


class TestUnreleasedTypoGate:
    """The gate fails on a seed-dependent token, but only in ``## Unreleased``."""

    def test_the_repo_changelog_passes(self):
        """This repo's own Unreleased section must already satisfy the gate."""
        checker = _load_checker()
        assert checker.main([str(project_root / "CHANGELOG.md")]) == 0

    def test_a_seed_dependent_token_in_unreleased_fails(self, tmp_path, capsys):
        checker = _load_checker()
        path = _changelog(
            tmp_path,
            f"### Fixed\n\n- **Bad entry**\n  - two latent {SEED_DEPENDENT} remain\n",
        )
        assert checker.main([str(path)]) == 1
        err = capsys.readouterr().err
        assert "mis" in err
        # Reported against the real file, at its real line number (the gate
        # blanks out-of-section lines rather than slicing the file).
        line_no = next(
            i
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
            if SEED_DEPENDENT in line
        )
        assert f"{path}:{line_no}:" in err

    def test_the_same_token_in_a_released_section_passes(self, tmp_path):
        """Released entries are immutable and legitimately allowlisted."""
        checker = _load_checker()
        path = _changelog(
            tmp_path,
            "### Fixed\n\n- **Good entry**\n  - nothing to report\n",
            RELEASED_SECTION.format(token=SEED_DEPENDENT),
        )
        assert checker.main([str(path)]) == 0

    def test_a_changelog_without_an_unreleased_section_passes(self, tmp_path):
        """The release window: prepare-release renames Unreleased to a version."""
        checker = _load_checker()
        path = tmp_path / "CHANGELOG.md"
        path.write_text(
            HEADER + RELEASED_SECTION.format(token=SEED_DEPENDENT), encoding="utf-8"
        )
        assert checker.main([str(path)]) == 0
