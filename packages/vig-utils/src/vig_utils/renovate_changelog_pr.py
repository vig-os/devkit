"""Parse bot-PR metadata for changelog synthesis (Refs: #506, #1423).

Parsing library for Renovate dependency-update PRs and devkit adoption PRs
(``chore: adopt devkit X.Y.Z[-rcN]``, Refs: #1404). Since #1423 the entry
formatting, insertion and CLI live in ``synthesize_bot_changelog``, which
consumes these parsers at release cut and finalize.
"""

from __future__ import annotations

import re

# The devkit-upgrade workflow's PR title, verbatim: bare semver with an
# optional prerelease (devkit tags carry no `v` prefix). Anchored so arbitrary
# chore titles never masquerade as adoptions.
_ADOPTION_TITLE_RE = re.compile(
    r"^chore: adopt devkit (\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?)$"
)


def parse_adoption_title(title: str) -> str | None:
    """Return the devkit version from an adoption PR title, or None."""
    m = _ADOPTION_TITLE_RE.match(title.strip())
    if m:
        return m.group(1)
    return None


def _strip_md_link(cell: str) -> str:
    s = cell.strip()
    m = re.match(r"\[([^\]]+)\]\([^)]+\)", s)
    if m:
        return m.group(1).strip()
    return s


def _parse_change_cell(cell: str) -> tuple[str | None, str | None]:
    """Return (old, new) from a Renovate-style change cell."""
    text = cell.strip()
    # Renovate renders the arrow as U+2192 (→); accept ASCII -> as well.
    m = re.search(r"`([^`]+)`\s*(?:->|→)\s*`([^`]+)`", text)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    # Digest / unquoted: abc → def
    m = re.search(r"(\S+)\s*(?:->|→)\s*(\S+)", text)
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
