"""Shape pins for the BATS suite itself (#1697, #1699).

``bats`` 1.5 gates the ``run`` flags (``run -0``, ``run --separate-stderr``, …)
behind a ``bats_require_minimum_version`` declaration and prints a ``BW02``
warning for every use without one. The declaration must sit at file top level —
``test_helper.bash`` is ``load``ed from ``setup``, which runs far too late — so it
cannot be centralised and has to be repeated per file. One rule for all of them
(declare everywhere, not only where a flag happens to be used today) is what
keeps a later ``run -0`` from silently reintroducing the warning, so the rule is
pinned here rather than left to review.

The second pin refuses ``teardown_file`` outright (#1699). Its exit code is *not*
the problem: a plainly failing ``teardown_file`` does exit 1, on bats 1.12.0 and
1.14.0 alike (verified in #1699, which was filed on the opposite claim). The
problem is that three paths swallow such a failure whole — exit 0, and no
``not ok`` line to grep for either:

1. ``setup_file`` calls ``skip`` — the file's ``teardown_file`` status is
   discarded (deliberate upstream, bats-core#695).
2. ``--filter`` / ``--filter-status`` selects zero tests in the file — the file
   body, ``teardown_file`` included, never runs at all.
3. A command fails inside a pipeline (``false | cat``) — plain bash pipeline
   status, and bats sets no ``pipefail``.

An invariant asserted in ``teardown_file`` can therefore go unchecked while CI
stays green, so assertions belong in a test body instead. The allowlist below is
empty and is meant to stay that way; a ``teardown_file`` that only cleans up
still needs an entry, because nothing here can tell cleanup from assertion.

Refs: #1697, #1699
"""

from __future__ import annotations

import re
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

# Relative names (as printed in the parametrization ids) allowed to define a
# ``teardown_file``. Empty: see the module docstring before adding one.
TEARDOWN_FILE_ALLOWLIST: frozenset[str] = frozenset()

# A ``teardown_file`` function definition at the start of a line, in either bash
# spelling: ``teardown_file() {`` / ``teardown_file () {`` and
# ``function teardown_file {`` / ``function teardown_file() {``.
TEARDOWN_FILE_DEFINITION = re.compile(
    r"^\s*(?:function\s+teardown_file\b|teardown_file\s*\(\s*\))"
)


def _first_statement(path: Path) -> str | None:
    """First executable line of ``path``: shebang, blanks and comments skipped."""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        return line
    return None


def _defines_teardown_file(path: Path) -> bool:
    """Whether ``path`` defines a ``teardown_file`` function; comments ignored."""
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.strip().startswith("#"):
            continue
        if TEARDOWN_FILE_DEFINITION.match(raw):
            return True
    return False


def test_bats_suite_is_discovered() -> None:
    """The glob finds the suite — a silent zero-file parametrization passes."""
    assert len(BATS_FILES) >= 20, (
        f"expected at least 20 .bats files under {BATS_DIR}, found "
        f"{len(BATS_FILES)} — has the suite moved?"
    )


@pytest.mark.parametrize("path", BATS_FILES, ids=lambda p: str(p.relative_to(BATS_DIR)))
def test_bats_file_declares_minimum_version(path: Path) -> None:
    """Every .bats file declares the minimum version as its first statement."""
    assert _first_statement(path) == REQUIRED_DECLARATION, (
        f"{path.relative_to(REPO_ROOT)} must declare `{REQUIRED_DECLARATION}` as "
        f"its first statement (after the header comment, before setup); found "
        f"{_first_statement(path)!r}"
    )


@pytest.mark.parametrize("path", BATS_FILES, ids=lambda p: str(p.relative_to(BATS_DIR)))
def test_bats_file_defines_no_teardown_file(path: Path) -> None:
    """No .bats file defines ``teardown_file`` — its failures can be swallowed.

    Three paths discard a ``teardown_file`` failure with exit 0 and no ``not ok``
    line: a ``skip`` in ``setup_file`` (deliberate upstream, bats-core#695), a
    ``--filter``/``--filter-status`` that selects zero tests in the file, and a
    command failing inside a pipeline (bats sets no ``pipefail``). An invariant
    asserted there can go unchecked while the run stays green, so it belongs in a
    test body. The exit code itself is not the problem: a plainly failing
    ``teardown_file`` does exit 1 on bats 1.12.0 and 1.14.0 (verified in #1699).
    """
    name = str(path.relative_to(BATS_DIR))
    if name in TEARDOWN_FILE_ALLOWLIST:
        return
    assert not _defines_teardown_file(path), (
        f"{path.relative_to(REPO_ROOT)} defines `teardown_file`, whose failures "
        f"bats can swallow with exit 0 (see this module's docstring and #1699) — "
        f"assert in a test body instead, or add {name!r} to "
        f"TEARDOWN_FILE_ALLOWLIST if it only cleans up"
    )


@pytest.mark.parametrize(
    ("body", "defines"),
    [
        ("teardown_file() {\n  true\n}\n", True),
        ("teardown_file () {\n", True),
        ("    teardown_file() {\n", True),
        ("function teardown_file {\n", True),
        ("function teardown_file() {\n", True),
        ("# teardown_file() {\n", False),
        ("  #teardown_file() {\n", False),
        ("# function teardown_file {\n", False),
        ('echo "teardown_file() {"\n', False),
        ("teardown() {\n", False),
        ("teardown_file_helper() {\n", False),
        ("function teardown_file_helper {\n", False),
    ],
)
def test_teardown_file_matcher(tmp_path: Path, body: str, defines: bool) -> None:
    """The matcher sees real definitions and not mentions of the name."""
    candidate = tmp_path / "candidate.bats"
    candidate.write_text(body, encoding="utf-8")
    assert _defines_teardown_file(candidate) is defines
