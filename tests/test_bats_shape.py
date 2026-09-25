"""Shape pins for the BATS suite itself (#1697).

``bats`` 1.5 gates the ``run`` flags (``run -0``, ``run --separate-stderr``, …)
behind a ``bats_require_minimum_version`` declaration and prints a ``BW02``
warning for every use without one. The declaration must sit at file top level —
``test_helper.bash`` is ``load``ed from ``setup``, which runs far too late — so it
cannot be centralised and has to be repeated per file. One rule for all of them
(declare everywhere, not only where a flag happens to be used today) is what
keeps a later ``run -0`` from silently reintroducing the warning, so the rule is
pinned here rather than left to review.

Refs: #1697
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Repository root (tests/ -> repo root) and the BATS suite.
REPO_ROOT = Path(__file__).resolve().parent.parent
BATS_DIR = REPO_ROOT / "tests" / "bats"

BATS_FILES = sorted(BATS_DIR.glob("*.bats"))

# The minimum the suite declares. bats' own docs pin the feature set to 1.5.0;
# the flake ships a much newer bats, so the floor is a compatibility statement,
# not a version bump lever.
REQUIRED_DECLARATION = "bats_require_minimum_version 1.5.0"


def _first_statement(path: Path) -> str | None:
    """First executable line of ``path``: shebang, blanks and comments skipped."""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        return line
    return None


def test_bats_suite_is_discovered() -> None:
    """The glob finds the suite — a silent zero-file parametrization passes."""
    assert len(BATS_FILES) >= 20


@pytest.mark.parametrize("path", BATS_FILES, ids=lambda p: str(p.relative_to(BATS_DIR)))
def test_bats_file_declares_minimum_version(path: Path) -> None:
    """Every .bats file declares the minimum version as its first statement."""
    assert _first_statement(path) == REQUIRED_DECLARATION
