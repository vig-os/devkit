"""Parse Renovate PR metadata and insert a Keep-a-Changelog entry (Refs: #506)."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path


def _strip_md_link(cell: str) -> str:
    s = cell.strip()
    m = re.match(r"\[([^\]]+)\]\([^)]+\)", s)
    if m:
        return m.group(1).strip()
    return s


def _parse_change_cell(cell: str) -> tuple[str | None, str | None]:
    """Return (old, new) from a Renovate-style change cell."""
    text = cell.strip()
    m = re.search(r"`([^`]+)`\s*->\s*`([^`]+)`", text)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    # Digest / unquoted: abc -> def
    m = re.search(r"(\S+)\s*->\s*(\S+)", text)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return None, None


def _parse_table_updates(body: str) -> list[tuple[str, str | None, str | None]]:
    rows: list[tuple[str, str | None, str | None]] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            continue
        parts = [p.strip() for p in line.split("|")]
        # leading/trailing empty from split
        cells = [c for c in parts if c != ""]
        if len(cells) < 2:
            continue
        if re.match(r"^-+$", cells[0].replace(" ", "")):
            continue
        first = _strip_md_link(cells[0])
        if first.lower() in ("package", "name", "dependency"):
            continue
        old_v, new_v = None, None
        for cell in reversed(cells):
            o, n = _parse_change_cell(cell)
            if o is not None and n is not None:
                old_v, new_v = o, n
                break
        if new_v is not None:
            rows.append((first, old_v, new_v))
    return rows


def _parse_title_updates(title: str) -> list[tuple[str, str | None, str | None]]:
    t = title.strip()
    # digest: update actions/checkout digest to <sha>
    m = re.search(
        r"update\s+([^\s]+)\s+digest\s+to\s+(\S+)",
        t,
        re.IGNORECASE,
    )
    if m:
        return [(m.group(1), None, m.group(2))]
    # update dependency <pkg> to <ver>
    m = re.search(
        r"update\s+dependency\s+(\S+)\s+to\s+(\S+)",
        t,
        re.IGNORECASE,
    )
    if m:
        return [(m.group(1), None, m.group(2))]
    # update <pkg> to <ver> (no "dependency")
    m = re.search(r"update\s+(\S+)\s+to\s+(\S+)", t, re.IGNORECASE)
    if m:
        return [(m.group(1), None, m.group(2))]
    return []


def parse_renovate_pr_updates(
    title: str, body: str
) -> list[tuple[str, str | None, str | None]]:
    from_table = _parse_table_updates(body)
    if from_table:
        return from_table
    return _parse_title_updates(title)


def format_changelog_entry(
    pr_number: int,
    repo_html_url: str,
    updates: list[tuple[str, str | None, str | None]],
) -> str:
    base = repo_html_url.rstrip("/")
    pr_url = f"{base}/pull/{pr_number}"
    pr_link = f"([#{pr_number}]({pr_url}))"
    if len(updates) == 1:
        pkg, old_v, new_v = updates[0]
        if old_v:
            title = f"Renovate: update `{pkg}` from `{old_v}` to `{new_v}`"
        else:
            title = f"Renovate: update `{pkg}` to `{new_v}`"
        return f"- **{title}** {pr_link}\n"
    lines = [f"- **Renovate dependency update** {pr_link}"]
    for pkg, old_v, new_v in updates:
        if old_v:
            lines.append(f"  - Update `{pkg}` from `{old_v}` to `{new_v}`")
        else:
            lines.append(f"  - Update `{pkg}` to `{new_v}`")
    return "\n".join(lines) + "\n"


def _pr_marked_in_changed(unreleased: str, pr_number: int) -> bool:
    needle = f"[#{pr_number}]("
    changed_idx = unreleased.find("### Changed")
    if changed_idx == -1:
        return False
    next_hdr = re.search(r"\n### (?!Changed)\w+", unreleased[changed_idx:])
    if next_hdr:
        changed_block = unreleased[changed_idx : changed_idx + next_hdr.start()]
    else:
        changed_block = unreleased[changed_idx:]
    return needle in changed_block


def insert_renovate_changelog_entry(
    changelog: str,
    pr_number: int,
    entry: str,
) -> tuple[str, bool]:
    lines = changelog.splitlines(keepends=True)
    unreleased_start: int | None = None
    unreleased_end: int | None = None
    for i, line in enumerate(lines):
        if line.startswith("## Unreleased"):
            unreleased_start = i
            break
    if unreleased_start is None:
        return changelog, False
    for j in range(unreleased_start + 1, len(lines)):
        if lines[j].startswith("## [") and "[Unreleased]" not in lines[j]:
            unreleased_end = j
            break
    if unreleased_end is None:
        unreleased_end = len(lines)
    block = "".join(lines[unreleased_start:unreleased_end])
    if _pr_marked_in_changed(block, pr_number):
        return changelog, False

    changed_idx: int | None = None
    for i in range(unreleased_start, unreleased_end):
        if lines[i].startswith("### Changed"):
            changed_idx = i
            break
    if changed_idx is None:
        return changelog, False

    # Insert at the TOP of ### Changed, as a plain bullet above any #### sub-heading
    # (e.g. the #### Modules convention) rather than appended at the bottom of the
    # block. Keep the blank line after the heading for Keep-a-Changelog spacing.
    insert_at = changed_idx + 1
    if insert_at < len(lines) and lines[insert_at].strip() == "":
        insert_at += 1

    if not entry.endswith("\n"):
        entry = entry + "\n"

    # When the section opens with a heading (empty ### Changed, or a #### sub-heading
    # as its first content), append a blank line so the new bullet keeps Keep-a-Changelog
    # spacing before that heading.
    addition = [entry]
    if insert_at < len(lines) and lines[insert_at].lstrip().startswith("#"):
        addition.append("\n")

    new_lines = lines[:insert_at] + addition + lines[insert_at:]
    return "".join(new_lines), True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--changelog",
        default=os.environ.get("CHANGELOG_PATH", "CHANGELOG.md"),
        help="Path to CHANGELOG.md",
    )
    parser.add_argument(
        "--pr-number",
        type=int,
        default=int(os.environ.get("PR_NUMBER", "0")),
    )
    parser.add_argument(
        "--title",
        default=os.environ.get("PR_TITLE", ""),
    )
    parser.add_argument(
        "--body-file",
        default=os.environ.get("PR_BODY_FILE", ""),
        help="Path to file with PR body (optional)",
    )
    parser.add_argument(
        "--body",
        default=os.environ.get("PR_BODY", ""),
    )
    parser.add_argument(
        "--repo-url",
        default=os.environ.get("GITHUB_REPOSITORY_URL", ""),
        help="e.g. https://github.com/owner/repo",
    )
    args = parser.parse_args(argv)
    if args.pr_number <= 0:
        print("PR_NUMBER must be set", file=sys.stderr)
        return 1
    if not args.repo_url:
        print("GITHUB_REPOSITORY_URL must be set", file=sys.stderr)
        return 1
    body = args.body
    if args.body_file:
        body = Path(args.body_file).read_text(encoding="utf-8")
    updates = parse_renovate_pr_updates(args.title, body)
    if not updates:
        print("No dependency updates parsed; skipping changelog edit", file=sys.stderr)
        return 0
    entry = format_changelog_entry(args.pr_number, args.repo_url, updates)
    path = Path(args.changelog)
    text = path.read_text(encoding="utf-8")
    new_text, did = insert_renovate_changelog_entry(text, args.pr_number, entry)
    if not did:
        print("Changelog already contains entry for this PR or Unreleased malformed")
        return 0
    path.write_text(new_text, encoding="utf-8")
    print(f"Updated {path} for PR #{args.pr_number}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
