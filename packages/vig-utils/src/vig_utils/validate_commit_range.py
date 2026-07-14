#!/usr/bin/env python3
"""Validate every commit a pull request carries, plus its title.

The commit-msg hook only fires on a developer's machine, and `prek run
--all-files` never runs commit-msg-stage hooks -- so a broken (or absent)
`core.hooksPath` silently disabled commit-message validation entirely. This
entry point is the CI half of the guard: it re-validates the messages that a
PR actually proposes to write into history.

Two exemptions keep the check honest (see docs/COMMIT_MESSAGE_STANDARD.md):

* **Merge commits** are skipped. Their subject is the PR title, which is
  validated separately via ``--title``.
* **Bot-authored commits** are skipped. Renovate, Dependabot and
  commit-action-bot emit ``build(pip): ...`` / ``ci(actions): ...`` with no
  ``Refs:`` line; they cannot know an issue number, and holding them to the
  human rule would fail every dependency PR.

Usage:
    validate-commit-range --base <sha> --head <sha> [--title "<pr title>"]

Examples:
    validate-commit-range --base origin/dev --head HEAD
    validate-commit-range --base "$BASE_SHA" --head "$HEAD_SHA" --title "$PR_TITLE"
    validate-commit-range --title "feat(ci): add a lane"
"""

from __future__ import annotations

import argparse
import subprocess  # nosec B404 - fixed `git log` argv, no shell, no user input in argv[0]
import sys
from dataclasses import dataclass, field
from pathlib import Path

from vig_utils.utils import load_blocklist
from vig_utils.validate_commit_msg import (
    DEFAULT_APPROVED_TYPES,
    DEFAULT_REFS_OPTIONAL_TYPES,
    validate_commit_message,
)

# GitHub suffixes every bot account's name with "[bot]". A suffix rule beats a
# hardcoded roster: Renovate invents a scope per ecosystem and new bots appear
# without a config change here.
BOT_AUTHOR_SUFFIX = "[bot]"

# Unit/record separators: `git log` field data may contain newlines (a commit
# body does), so neither delimiter can be a newline.
_FIELD_SEP = "\x1f"
_RECORD_SEP = "\x1e"
_GIT_LOG_FORMAT = f"%H{_FIELD_SEP}%an{_FIELD_SEP}%P{_FIELD_SEP}%B{_RECORD_SEP}"


@dataclass(frozen=True)
class Commit:
    """One commit from the range under validation."""

    sha: str
    author: str
    message: str
    parents: tuple[str, ...] = field(default=())

    @property
    def is_merge(self) -> bool:
        return len(self.parents) > 1

    @property
    def subject(self) -> str:
        return self.message.strip().splitlines()[0] if self.message.strip() else ""


def is_bot_author(author: str) -> bool:
    """True if ``author`` is a GitHub bot account (``…[bot]``)."""
    return author.strip().endswith(BOT_AUTHOR_SUFFIX)


def parse_git_log(raw: str) -> list[Commit]:
    """Parse ``git log --format=_GIT_LOG_FORMAT`` output into commits."""
    commits: list[Commit] = []
    for record in raw.split(_RECORD_SEP):
        if not record.strip():
            continue
        sha, author, parents, message = record.lstrip("\n").split(_FIELD_SEP, 3)
        commits.append(
            Commit(
                sha=sha,
                author=author,
                message=message,
                parents=tuple(parents.split()),
            )
        )
    return commits


def read_commits(base: str, head: str, repo: Path | None = None) -> list[Commit]:
    """Read ``base..head`` from git."""
    result = subprocess.run(  # nosec B603 B607 - fixed argv, shell=False
        ["git", "log", f"--format={_GIT_LOG_FORMAT}", f"{base}..{head}"],
        capture_output=True,
        text=True,
        check=True,
        cwd=repo,
    )
    return parse_git_log(result.stdout)


def validate_commits(
    commits: list[Commit],
    approved_types: frozenset[str] | None = None,
    refs_optional_types: frozenset[str] | None = None,
    blocked_patterns: dict | None = None,
) -> list[tuple[Commit, str]]:
    """Validate each non-merge, non-bot commit. Returns (commit, error) failures."""
    failures: list[tuple[Commit, str]] = []
    for commit in commits:
        if commit.is_merge or is_bot_author(commit.author):
            continue
        valid, error = validate_commit_message(
            commit.message,
            approved_types=approved_types,
            refs_optional_types=refs_optional_types,
            blocked_patterns=blocked_patterns,
        )
        if not valid:
            failures.append((commit, error or "invalid commit message"))
    return failures


def validate_title(
    title: str,
    approved_types: frozenset[str] | None = None,
    blocked_patterns: dict | None = None,
) -> str | None:
    """Validate a PR title's subject line. Returns an error, or None if valid.

    A PR title is a bare subject -- there is nowhere to put a ``Refs:`` line --
    so the Refs rule cannot apply. Marking every approved type Refs-optional
    reuses the one validator to check exactly what a title can carry: the type,
    the scope charset, and the agent blocklist. The title still matters: PRs
    merge --no-ff, so it becomes the merge commit's subject in `dev`.
    """
    if approved_types is None:
        approved_types = DEFAULT_APPROVED_TYPES
    valid, error = validate_commit_message(
        title,
        approved_types=approved_types,
        refs_optional_types=approved_types,
        blocked_patterns=blocked_patterns,
    )
    return None if valid else (error or "invalid pull request title")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate the commit messages and title of a pull request."
    )
    parser.add_argument("--base", help="Base ref/sha of the range (exclusive).")
    parser.add_argument("--head", default="HEAD", help="Head ref/sha (inclusive).")
    parser.add_argument("--title", help="Pull request title to validate.")
    parser.add_argument(
        "--types",
        help="Comma-separated approved commit types.",
    )
    parser.add_argument(
        "--refs-optional-types",
        help="Comma-separated types where the Refs line is optional.",
    )
    parser.add_argument(
        "--blocked-patterns",
        type=Path,
        help="Path to the agent blocklist TOML.",
    )
    args = parser.parse_args(argv)

    if not args.base and not args.title:
        parser.error("nothing to validate: pass --base (with --head) and/or --title")

    approved_types = (
        frozenset(t.strip() for t in args.types.split(",") if t.strip())
        if args.types
        else DEFAULT_APPROVED_TYPES
    )
    refs_optional_types = (
        frozenset(t.strip() for t in args.refs_optional_types.split(",") if t.strip())
        if args.refs_optional_types
        else DEFAULT_REFS_OPTIONAL_TYPES
    )
    blocked_patterns = (
        load_blocklist(args.blocked_patterns)
        if args.blocked_patterns and args.blocked_patterns.exists()
        else None
    )

    errors: list[str] = []

    if args.title:
        error = validate_title(
            args.title,
            approved_types=approved_types,
            blocked_patterns=blocked_patterns,
        )
        if error:
            errors.append(f"Pull request title: {args.title!r}\n  {error}")

    if args.base:
        try:
            commits = read_commits(args.base, args.head)
        except subprocess.CalledProcessError as exc:
            print(
                f"git log {args.base}..{args.head} failed: {exc.stderr}",
                file=sys.stderr,
            )
            return 2
        failures = validate_commits(
            commits,
            approved_types=approved_types,
            refs_optional_types=refs_optional_types,
            blocked_patterns=blocked_patterns,
        )
        errors.extend(
            f"Commit {commit.sha[:8]}: {commit.subject!r}\n  {error}"
            for commit, error in failures
        )

    if errors:
        print(
            "Commit message validation failed "
            f"({len(errors)} problem{'s' if len(errors) > 1 else ''}):\n",
            file=sys.stderr,
        )
        for error in errors:
            print(f"{error}\n", file=sys.stderr)
        print(
            "See docs/COMMIT_MESSAGE_STANDARD.md for the standard.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
