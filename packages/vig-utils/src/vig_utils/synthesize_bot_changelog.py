"""Synthesize bot-PR changelog entries at release time (Refs: #1423).

Replaces the per-PR Renovate changelog pipeline: at release cut and finalize,
the merged bot-PR window since the last stable tag is enumerated from git
history, PR metadata is fetched via ``gh api``, and the result is rendered as
a regenerated ``#### Dependencies`` block inside ``### Changed`` — coalesced
to the net delta per dependency, because intermediate versions never shipped
in any published release. Hand-written entries are never touched: the block
is the synthesizer's only owned region and is rebuilt wholesale on every run,
which makes re-runs (re-cut, re-finalize) idempotent by construction.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from vig_utils.prepare_changelog import STANDARD_SECTIONS
from vig_utils.renovate_changelog_pr import (
    parse_adoption_title,
    parse_renovate_pr_updates,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

BOT_AUTHORS = frozenset({"renovate[bot]", "vigos-devkit-upgrade[bot]"})

# A squash-merge suffix (trailing "(#N)") or an explicit merge-commit subject.
# Mid-sentence "#N" is an issue reference and must never be treated as a PR.
_PR_SUFFIX_RE = re.compile(r"\(#(\d+)\)\s*$")
_MERGE_SUBJECT_RE = re.compile(r"^Merge pull request #(\d+)\b")

# Conventional-commit lockfile-maintenance titles: the scope names the
# ecosystem ("build(pip): lock file maintenance"). Renovate's unprefixed
# default ("Lock file maintenance") carries no scope. Anchored so titles that
# merely mention lock files never match.
_LOCKFILE_TITLE_RE = re.compile(
    r"^(?:\w+(?:\(([^)]+)\))?!?:\s*)?lock file maintenance$", re.IGNORECASE
)


@dataclass(frozen=True)
class BotPr:
    """The PR metadata the synthesizer consumes."""

    number: int
    author: str
    title: str
    body: str
    merged_at: str


@dataclass(frozen=True)
class DepDelta:
    """Net change of one dependency across the window."""

    name: str
    old: str | None
    new: str
    prs: list[int]


@dataclass(frozen=True)
class LockfileRollup:
    """All lockfile-maintenance PRs of one ecosystem scope."""

    scope: str
    prs: list[int]


@dataclass(frozen=True)
class AdoptionRollup:
    """Devkit adoptions coalesced to the version that actually ships."""

    version: str
    prs: list[int]


@dataclass(frozen=True)
class Coalesced:
    deps: list[DepDelta]
    lockfiles: list[LockfileRollup]
    adoptions: AdoptionRollup | None


def pr_numbers_from_subjects(subjects: Iterable[str]) -> list[int]:
    """PR numbers referenced by merge/squash subjects, deduplicated in order."""
    numbers: list[int] = []
    for subject in subjects:
        m = _PR_SUFFIX_RE.search(subject) or _MERGE_SUBJECT_RE.match(subject)
        if m:
            n = int(m.group(1))
            if n not in numbers:
                numbers.append(n)
    return numbers


def last_stable_tag(tags: Iterable[str], tag_prefix: str = "") -> str | None:
    """The highest reachable stable ``<prefix>X.Y.Z`` tag, or None.

    Prereleases are excluded on purpose: mid-train, the branch already carries
    this train's own rc tags, and a window starting at an rc would hide every
    bot PR merged before it.
    """
    stable = re.compile(re.escape(tag_prefix) + r"(\d+)\.(\d+)\.(\d+)$")
    best: tuple[int, int, int] | None = None
    best_tag: str | None = None
    for tag in tags:
        m = stable.fullmatch(tag.strip())
        if not m:
            continue
        version = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if best is None or version > best:
            best, best_tag = version, tag.strip()
    return best_tag


def parse_lockfile_title(title: str) -> str | None:
    """The ecosystem scope of a lockfile-maintenance title, '' if unscoped."""
    m = _LOCKFILE_TITLE_RE.match(title.strip())
    if not m:
        return None
    return m.group(1) or ""


def coalesce(prs: Iterable[BotPr]) -> Coalesced:
    """Fold the window's bot PRs into net-delta entries.

    Only the net delta since the last release counts: the ``from`` side comes
    from the earliest PR touching a dependency, the ``to`` side from the
    latest, and every contributing PR is cited. A dependency bumped and then
    bumped back nets to zero and disappears.
    """
    ordered = sorted(
        (p for p in prs if p.author in BOT_AUTHORS),
        key=lambda p: (p.merged_at, p.number),
    )
    deps: dict[str, dict] = {}
    lockfiles: dict[str, list[int]] = {}
    adoption_prs: list[int] = []
    adoption_version: str | None = None
    for pr in ordered:
        version = parse_adoption_title(pr.title)
        if version is not None:
            adoption_prs.append(pr.number)
            adoption_version = version
            continue
        scope = parse_lockfile_title(pr.title)
        if scope is not None:
            lockfiles.setdefault(scope, []).append(pr.number)
            continue
        for name, old, new in parse_renovate_pr_updates(pr.title, pr.body):
            entry = deps.setdefault(name, {"old": old, "new": new, "prs": []})
            entry["new"] = new
            if pr.number not in entry["prs"]:
                entry["prs"].append(pr.number)
    return Coalesced(
        deps=[
            DepDelta(name=name, old=e["old"], new=e["new"], prs=e["prs"])
            for name, e in deps.items()
            if e["old"] is None or e["old"] != e["new"]
        ],
        lockfiles=[
            LockfileRollup(scope=scope, prs=numbers)
            for scope, numbers in lockfiles.items()
        ],
        adoptions=(
            AdoptionRollup(version=adoption_version, prs=adoption_prs)
            if adoption_version is not None
            else None
        ),
    )


def render_dependencies_block(coalesced: Coalesced, repo_html_url: str) -> str | None:
    """The regenerated ``#### Dependencies`` block, or None when empty."""
    if not (coalesced.deps or coalesced.lockfiles or coalesced.adoptions):
        return None
    base = repo_html_url.rstrip("/")

    def links(numbers: list[int]) -> str:
        return ", ".join(f"[#{n}]({base}/pull/{n})" for n in numbers)

    lines = ["#### Dependencies", ""]
    for dep in coalesced.deps:
        if dep.old:
            lines.append(
                f"- Update `{dep.name}` from `{dep.old}` to `{dep.new}`"
                f" ({links(dep.prs)})"
            )
        else:
            lines.append(f"- Update `{dep.name}` to `{dep.new}` ({links(dep.prs)})")
    for rollup in coalesced.lockfiles:
        label = (
            f"Lock file maintenance ({rollup.scope})"
            if rollup.scope
            else "Lock file maintenance"
        )
        lines.append(f"- {label} ({links(rollup.prs)})")
    if coalesced.adoptions:
        version = coalesced.adoptions.version
        notes = f"https://github.com/vig-os/devkit/releases/tag/{version}"
        lines.append(
            f"- Adopt vigOS devkit {version} ({links(coalesced.adoptions.prs)})"
            f" — [release notes]({notes})"
        )
    return "\n".join(lines) + "\n"


def _target_section_bounds(lines: list[str], version: str | None) -> tuple[int, int]:
    if version is None:
        start = next(
            (i for i, line in enumerate(lines) if line.startswith("## Unreleased")),
            None,
        )
        if start is None:
            raise ValueError("no '## Unreleased' heading in changelog")
    else:
        heading = f"## [{version}] - TBD"
        start = next(
            (i for i, line in enumerate(lines) if line.rstrip("\n") == heading), None
        )
        if start is None:
            raise ValueError(f"no '{heading}' heading in changelog")
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    return start, end


def _remove_existing_block(lines: list[str], start: int, end: int) -> int:
    """Drop an existing ``#### Dependencies`` block; return the new end."""
    for i in range(start, end):
        if lines[i].rstrip("\n") == "#### Dependencies":
            j = i + 1
            while j < end and not lines[j].startswith(("#### ", "### ", "## ")):
                j += 1
            # Also absorb one preceding blank line so removal leaves no
            # double blank between the neighbors.
            if i > start and lines[i - 1].strip() == "":
                i -= 1
            del lines[i:j]
            return end - (j - i)
    return end


def splice_dependencies_block(
    changelog: str, block: str | None, version: str | None
) -> str:
    """Rebuild the synthesizer-owned block inside the target section.

    ``version`` selects the frozen ``## [X.Y.Z] - TBD`` section (finalize on
    the release branch); None selects ``## Unreleased`` (cut). Regeneration —
    remove-then-insert — rather than insert-if-missing is what lets a
    mid-train bot PR extend an already-synthesized coalesced entry.
    """
    lines = changelog.splitlines(keepends=True)
    start, end = _target_section_bounds(lines, version)
    end = _remove_existing_block(lines, start, end)
    if block is None:
        return "".join(lines)

    block_lines = [line + "\n" for line in block.rstrip("\n").split("\n")]
    changed_idx = next(
        (i for i in range(start, end) if lines[i].rstrip("\n") == "### Changed"),
        None,
    )
    if changed_idx is None:
        # The frozen section only carries subsections that had content:
        # create ### Changed at its Keep-a-Changelog position.
        changed_rank = STANDARD_SECTIONS.index("Changed")
        insert_at = end
        for i in range(start, end):
            m = re.match(r"^### (\w+)", lines[i])
            if (
                m
                and m.group(1) in STANDARD_SECTIONS
                and STANDARD_SECTIONS.index(m.group(1)) > changed_rank
            ):
                insert_at = i
                break
        addition = ["### Changed\n", "\n", *block_lines, "\n"]
        while insert_at > start + 1 and lines[insert_at - 1].strip() == "":
            insert_at -= 1
            addition = addition[:-1] if addition[-1] == "\n" else addition
            addition.append("\n")
        lines[insert_at:insert_at] = addition
        return "".join(lines)

    insert_at = end
    for i in range(changed_idx + 1, end):
        if lines[i].startswith(("### ", "## ")):
            insert_at = i
            break
    # Land after the section's existing content with exactly one blank line on
    # each side of the block.
    content_end = insert_at
    while content_end > changed_idx + 1 and lines[content_end - 1].strip() == "":
        content_end -= 1
    tail = ["\n"] if insert_at < len(lines) else []
    lines[content_end:insert_at] = ["\n", *block_lines, *tail]
    return "".join(lines)


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)  # noqa: S603


def _fetch_pr(repo: str | None, number: int) -> BotPr | None:
    path = (
        f"repos/{repo}/pulls/{number}"
        if repo
        else f"repos/{{owner}}/{{repo}}/pulls/{number}"
    )
    proc = _run(["gh", "api", path])
    if proc.returncode != 0:
        # Not every "(#N)" resolves to a PR (plain issue refs 404); skip.
        return None
    data = json.loads(proc.stdout)
    if not data.get("merged_at"):
        return None
    return BotPr(
        number=int(data["number"]),
        author=str((data.get("user") or {}).get("login") or ""),
        title=str(data.get("title") or ""),
        body=str(data.get("body") or ""),
        merged_at=str(data["merged_at"]),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--changelog",
        default=os.environ.get("CHANGELOG_PATH", "CHANGELOG.md"),
        help="Path to CHANGELOG.md",
    )
    parser.add_argument(
        "--version",
        default=None,
        help="Target the frozen '## [VERSION] - TBD' section (finalize)",
    )
    parser.add_argument(
        "--tag-prefix",
        default=os.environ.get("TAG_PREFIX", ""),
        help="Tag prefix for the last-stable-tag window boundary",
    )
    parser.add_argument(
        "--repo-url",
        default=os.environ.get("GITHUB_REPOSITORY_URL", ""),
        help="e.g. https://github.com/owner/repo (for entry links)",
    )
    parser.add_argument(
        "--github-repository",
        default=os.environ.get("GITHUB_REPOSITORY", ""),
        help="owner/repo for gh api PR lookups",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the synthesized block without touching the changelog",
    )
    args = parser.parse_args(argv)

    path = Path(args.changelog)
    if not path.is_file():
        # Consumers without a changelog are a no-op, not an error.
        print(f"{path} not found; skipping changelog synthesis", file=sys.stderr)
        return 0
    if not args.repo_url:
        print("GITHUB_REPOSITORY_URL must be set", file=sys.stderr)
        return 1

    tags = _run(["git", "tag", "--merged", "HEAD"])
    if tags.returncode != 0:
        print(f"git tag failed: {tags.stderr.strip()}", file=sys.stderr)
        return 1
    boundary = last_stable_tag(tags.stdout.splitlines(), args.tag_prefix)
    window = f"{boundary}..HEAD" if boundary else "HEAD"
    log = _run(["git", "log", "--format=%s", window])
    if log.returncode != 0:
        print(f"git log failed: {log.stderr.strip()}", file=sys.stderr)
        return 1

    prs = []
    for number in pr_numbers_from_subjects(log.stdout.splitlines()):
        pr = _fetch_pr(args.github_repository or None, number)
        if pr is not None:
            prs.append(pr)

    block = render_dependencies_block(coalesce(prs), args.repo_url)
    if args.dry_run:
        print(block or "(no bot changelog entries in the window)")
        return 0
    text = path.read_text(encoding="utf-8")
    new_text = splice_dependencies_block(text, block, version=args.version)
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        print(f"Synthesized bot changelog entries in {path} (window {window})")
    else:
        print(f"No bot changelog changes for {path} (window {window})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
