#!/usr/bin/env python3
"""Validate a branch name against the topic-branch convention.

The ONE implementation of the branch-name rule (#1760). The local pre-commit
hook, the scaffolded CI ``Validate branch name`` step and devkit's own CI step
all call this entry point, so the accepted shapes cannot drift apart again.
Before it, the rule lived in a negative-lookahead regex in the hook and in
hand-kept ``ALLOWED`` bash alternations in CI, and they disagreed
(``release/X.Y.Z`` passed CI but not the hook).

A branch is accepted when it is one of:

* ``main``; ``dev`` too under the gitflow workflow model (a trunk workspace
  has no long-lived ``dev`` branch);
* ``<type>/<slug>`` for an issue-less type (``--issueless-types``: ``chore``
  plus every Refs-optional commit type, #1767);
* ``<type>/<issue>-<slug>`` for an issue-numbered type (``--types``,
  DEVKIT_BRANCH_TYPES);
* ``worktree/<issue>`` (the autonomous worktree pipeline);
* ``renovate/<anything>`` (Renovate's namespace, free-form names, #1433);
* ``release/X.Y.Z`` (release-train branches, bare semver).

A slug is lowercase alphanumeric words joined by single hyphens.

Pure arguments, no ``.vig-os`` reads -- the same contract as
``validate-commit-range``: each caller resolves the knobs and passes them in.

Usage:
    validate-branch-name [--branch NAME] [--types LIST]
                         [--issueless-types LIST] [--workflow gitflow|trunk]

Without ``--branch`` the checked-out branch is validated. A detached HEAD has
no branch to check and passes with a note, exactly like pre-commit-hooks'
``no-commit-to-branch`` it replaces.
"""

from __future__ import annotations

import argparse
import re
import subprocess  # nosec B404 - fixed `git symbolic-ref` argv, no shell
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

# The stock sets. MIRROR nix/hooks.nix `defaultBranchTypes` and
# assets/init-workspace.sh DEFAULT_BRANCH_TYPES (the issue-less floor is
# `chore`: the sync-main-to-dev and devkit-upgrade bot branches use it).
DEFAULT_BRANCH_TYPES: tuple[str, ...] = (
    "feature",
    "bugfix",
    "hotfix",
    "release",
    "docs",
    "test",
    "refactor",
)
DEFAULT_ISSUELESS_TYPES: tuple[str, ...] = ("chore",)
WORKFLOWS = ("gitflow", "trunk")

_SLUG = r"[a-z0-9]+(?:-[a-z0-9]+)*"
_FIXED_PATTERNS = (
    re.compile(r"worktree/[0-9]+"),
    re.compile(r"renovate/.+"),
    re.compile(r"release/[0-9]+\.[0-9]+\.[0-9]+"),
)


def _alternation(types: tuple[str, ...]) -> str:
    return "|".join(re.escape(t) for t in types)


def validate_branch_name(
    branch: str,
    types: tuple[str, ...] = DEFAULT_BRANCH_TYPES,
    issueless_types: tuple[str, ...] = DEFAULT_ISSUELESS_TYPES,
    workflow: str = "gitflow",
) -> str | None:
    """Return an error message for ``branch``, or None if it is valid."""
    long_lived = {"main"} if workflow == "trunk" else {"main", "dev"}
    if branch in long_lived:
        return None
    patterns = list(_FIXED_PATTERNS)
    if issueless_types:
        patterns.append(re.compile(rf"(?:{_alternation(issueless_types)})/{_SLUG}"))
    if types:
        patterns.append(re.compile(rf"(?:{_alternation(types)})/[0-9]+-{_SLUG}"))
    # fullmatch: `$` alone would accept a trailing newline.
    if any(p.fullmatch(branch) for p in patterns):
        return None
    return (
        f"Branch name {branch!r} does not follow the convention "
        f"<type>/<issue>-<summary> (types: {','.join(types)}) or "
        f"<type>/<summary> (types: {','.join(issueless_types)}). "
        "See docs/COMMIT_MESSAGE_STANDARD.md and the branch-naming skill."
    )


def current_branch(repo: Path | None = None) -> str | None:
    """The checked-out branch, or None on a detached HEAD / outside a repo."""
    try:
        result = subprocess.run(  # nosec B603 B607 - fixed argv, shell=False
            ["git", "symbolic-ref", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=repo,
        )
    except subprocess.CalledProcessError, FileNotFoundError:
        return None
    return result.stdout.strip() or None


def _split(value: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    """Comma-separated, whitespace-tolerant; empty falls back to ``default``."""
    if not value:
        return default
    items = tuple(t.strip() for t in value.split(",") if t.strip())
    return items or default


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a branch name against the topic-branch convention."
    )
    parser.add_argument(
        "--branch",
        help="Branch name to validate (default: the checked-out branch).",
    )
    parser.add_argument(
        "--types",
        help="Comma-separated issue-numbered branch types (<type>/<issue>-<slug>).",
    )
    parser.add_argument(
        "--issueless-types",
        help="Comma-separated issue-less branch types (<type>/<slug>).",
    )
    parser.add_argument(
        "--workflow",
        choices=WORKFLOWS,
        default="gitflow",
        help="Workflow model: gitflow also allows the long-lived dev branch.",
    )
    args = parser.parse_args(argv)

    branch = args.branch
    if branch is None:
        branch = current_branch()
        if branch is None:
            print(
                "validate-branch-name: detached HEAD (or not a git repository); "
                "no branch to check.",
                file=sys.stderr,
            )
            return 0

    error = validate_branch_name(
        branch,
        types=_split(args.types, DEFAULT_BRANCH_TYPES),
        issueless_types=_split(args.issueless_types, DEFAULT_ISSUELESS_TYPES),
        workflow=args.workflow,
    )
    if error:
        print(error, file=sys.stderr)
        return 1
    print(f"Branch name OK: {branch}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
