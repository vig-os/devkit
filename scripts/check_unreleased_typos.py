#!/usr/bin/env python3
"""Lint the changelog's ``## Unreleased`` section with no typos allowlist (#1534).

Devkit's ``CHANGELOG.md`` is manifest-synced into the scaffold
(``assets/workspace/.devcontainer/CHANGELOG.md``) and devcontainer-mode consumers
**git-track** that copy, so their own typos hook has to lint it against a
``.typos.toml`` that is seeded once and never overwritten by an upgrade. A word
that lints only under an allowlist entry devkit added later therefore breaks such
a consumer's upgrade at the commit step (#1529) — and a released changelog entry
is immutable by policy, so it can never be reworded afterwards. Catching it after
the release is useless; the only place to catch it is before the text is
committed.

Hence this gate: the ``## Unreleased`` section, linted with ``typos --isolated``
(no config, no allowlist), so nothing that needs one can ever be frozen into a
release. Scope is the Unreleased section ONLY — released sections legitimately
carry allowlisted tokens (1.10.0's ``mis-parses``, which the manifest transform
sanitizes in the synced copy) and must not fail the gate. A changelog with no
Unreleased section at all (the release window, where prepare-release has renamed
it to ``## [X.Y.Z]``) has nothing to check and passes.

Lines outside the section are blanked rather than dropped, so typos reports the
real line numbers of the real file.

Usage:
    uv run python scripts/check_unreleased_typos.py [CHANGELOG.md]

Called by:
    - the check-unreleased-typos pre-commit hook (nix/hooks.nix; devkit-only)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# Section boundaries, as in vig_utils.prepare_changelog: the Unreleased block
# runs from its own heading to the next top-level (``## ``) heading.
UNRELEASED_HEADING = "## Unreleased"
SECTION_PREFIX = "## "

TYPOS_ARGV = ["typos", "--isolated", "--format", "brief", "-"]

ADVICE = (
    "The `## Unreleased` text above needs a typos allowlist entry to lint. Once "
    "released it is immutable, and it is synced into every devcontainer-mode "
    "consumer's worktree (.devcontainer/CHANGELOG.md), where a `.typos.toml` "
    "seeded before that entry cannot lint it — the #1529 upgrade break. Reword "
    "the entry instead of extending .typos.toml (#1534)."
)


def mask_outside_unreleased(text: str) -> str | None:
    """Blank every line outside ``## Unreleased``, or return None if absent.

    Line count is preserved so typos' line numbers match the source file.
    """
    inside = False
    seen = False
    masked: list[str] = []
    for line in text.splitlines():
        if line.strip() == UNRELEASED_HEADING:
            inside = True
            seen = True
            masked.append("")
            continue
        if inside and line.startswith(SECTION_PREFIX):
            inside = False
        masked.append(line if inside else "")
    if not seen:
        return None
    return "\n".join(masked) + "\n"


def _report(output: str, path: Path) -> None:
    """Print typos' findings, re-anchored from stdin (``-``) onto ``path``."""
    for line in output.splitlines():
        print(f"{path}:{line[2:]}" if line.startswith("-:") else line, file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "path",
        nargs="?",
        default="CHANGELOG.md",
        type=Path,
        help="changelog to check (default: CHANGELOG.md)",
    )
    args = parser.parse_args(argv)

    masked = mask_outside_unreleased(args.path.read_text(encoding="utf-8"))
    if masked is None:
        return 0

    try:
        result = subprocess.run(  # noqa: S603 - fixed argv, no shell
            TYPOS_ARGV, input=masked, capture_output=True, text=True, check=False
        )
    except FileNotFoundError:
        print(
            "check-unreleased-typos: `typos` not found on PATH (it ships in the "
            "devkit dev-shell/image toolchain)",
            file=sys.stderr,
        )
        return 1

    if result.returncode == 0:
        return 0
    _report(result.stdout, args.path)
    if result.stderr:
        print(result.stderr.rstrip(), file=sys.stderr)
    print(ADVICE, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
