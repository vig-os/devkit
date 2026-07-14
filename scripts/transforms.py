#!/usr/bin/env python3
"""Transform classes for file post-processing (used by sync_manifest)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from pathlib import Path

from vig_utils.utils import substitute_in_file


class Transform(Protocol):
    """A post-copy transformation applied to a synced file."""

    def apply(self, file_path: Path) -> None: ...


# ── Provenance banner (issue #1036) ───────────────────────────────────────────
#
# Two byte-stable, version-free variants stamped into comment-capable scaffold
# assets. The managed/preserved choice is derived from PRESERVE_FILES (the SSoT
# in assets/init-workspace.sh) by sync_manifest.py — never hand-written per file.
# The version deliberately lives only in .vig-os (DEVKIT_VERSION), so banners do
# not churn on every release.

MANAGED_BANNER: tuple[str, str] = (
    "Managed by vigOS devkit — regenerated on upgrade; local edits are lost.",
    "Customize in justfile.project. "
    "Bugs / missing tools: https://github.com/vig-os/devkit/issues",
)

PRESERVED_BANNER: tuple[str, str] = (
    "Seeded by vigOS devkit — yours to edit; upgrades never overwrite this file.",
    "Bugs / missing tools: https://github.com/vig-os/devkit/issues",
)

# Comment styles: (line prefix, line suffix). Strict-JSON files carry no comment
# syntax and are skip-listed by sync_manifest.py rather than handled here.
_COMMENT_STYLES: dict[str, tuple[str, str]] = {
    "hash": ("# ", ""),
    "html": ("<!-- ", " -->"),
    # JSONC (#1053): VS Code and the devcontainer CLI accept `//` line comments
    # in these config files. The banner sits above the root object; the strict
    # check-json hook is given an exclude for these paths (nix/hooks.nix).
    "jsonc": ("// ", ""),
}

# Every banner sentence, style-independent — used to recognise (and strip) an
# existing banner so the transform is idempotent and switches variants cleanly.
_BANNER_TEXTS: frozenset[str] = frozenset(MANAGED_BANNER + PRESERVED_BANNER)


def _banner_inner(line: str) -> str | None:
    """Return a comment line's inner text, or None if it is not a comment."""
    stripped = line.strip()
    if stripped.startswith("<!--") and stripped.endswith("-->"):
        return stripped[4:-3].strip()
    if stripped.startswith("//"):
        return stripped[2:].strip()
    if stripped.startswith("#"):
        return stripped.lstrip("#").strip()
    return None


def _split_header(lines: list[str], style: str) -> tuple[list[str], list[str]]:
    """Split off a leading region the banner must sit *after*.

    Shebangs, a YAML document-start marker (``---``) and markdown front matter
    all carry positional meaning, so the banner goes after them, not before.
    """
    if not lines:
        return [], []
    if style == "html":
        if lines[0].strip() == "---":
            for i in range(1, len(lines)):
                if lines[i].strip() == "---":
                    return lines[: i + 1], lines[i + 1 :]
        return [], lines
    # hash style
    idx = 1 if lines[0].startswith("#!") else 0
    probe = idx
    while probe < len(lines) and lines[probe].strip() == "":
        probe += 1
    if probe < len(lines) and lines[probe].strip() == "---":
        return lines[: probe + 1], lines[probe + 1 :]
    return lines[:idx], lines[idx:]


def _strip_banner_block(rest: list[str]) -> list[str]:
    """Drop a leading run of banner lines (any style) plus one trailing blank."""
    i = 0
    saw = False
    while i < len(rest) and _banner_inner(rest[i]) in _BANNER_TEXTS:
        i += 1
        saw = True
    if saw and i < len(rest) and rest[i].strip() == "":
        i += 1
    return rest[i:]


@dataclass
class Banner:
    """Stamp the generated provenance banner (#1036) for the given variant.

    Idempotent: an existing banner (of either variant/style) is stripped before
    the current one is inserted, so re-running the sync never stacks or drifts.
    """

    preserved: bool
    style: str = "hash"
    target: str = ""

    def apply(self, file_path: Path) -> None:
        path = _resolve(file_path, self.target)
        if path is None:
            return
        prefix, suffix = _COMMENT_STYLES[self.style]
        texts = PRESERVED_BANNER if self.preserved else MANAGED_BANNER
        banner = [f"{prefix}{t}{suffix}\n" for t in texts]

        original = path.read_text()
        header, rest = _split_header(original.splitlines(keepends=True), self.style)
        rest = _strip_banner_block(rest)
        while rest and rest[0].strip() == "":
            rest.pop(0)

        new_lines = header + banner
        if rest:
            new_lines += ["\n", *rest]
        result = "".join(new_lines)
        if original.endswith("\n") and not result.endswith("\n"):
            result += "\n"
        path.write_text(result)


def _resolve(file_path: Path, target: str) -> Path | None:
    """Resolve a transform target path, returning None if it doesn't exist."""
    path = file_path / target if target else file_path
    if not path.exists():
        return None
    return path


@dataclass
class Sed:
    """Regex substitution on a file (or a specific file within a directory entry)."""

    pattern: str
    replace: str
    target: str = ""

    def apply(self, file_path: Path) -> None:
        path = _resolve(file_path, self.target)
        if path is None:
            return
        substitute_in_file(path, self.pattern, self.replace, regex=True)


@dataclass
class RemoveLines:
    """Remove lines matching a regex pattern."""

    pattern: str
    target: str = ""

    def apply(self, file_path: Path) -> None:
        path = _resolve(file_path, self.target)
        if path is None:
            return
        content = path.read_text()
        lines = content.splitlines(keepends=True)
        filtered = [line for line in lines if not re.search(self.pattern, line)]
        path.write_text("".join(filtered))


@dataclass
class StripTrailingBlankLines:
    """Remove trailing blank lines from a file, keeping a single final newline."""

    target: str = ""

    def apply(self, file_path: Path) -> None:
        path = _resolve(file_path, self.target)
        if path is None:
            return
        content = path.read_text()
        path.write_text(content.rstrip() + "\n")


@dataclass
class RemoveBlock:
    """Remove a block of lines from start_pattern through end_pattern (inclusive)."""

    start_pattern: str
    end_pattern: str
    target: str = ""

    def apply(self, file_path: Path) -> None:
        path = _resolve(file_path, self.target)
        if path is None:
            return
        content = path.read_text()
        lines = content.splitlines(keepends=True)
        result = []
        skipping = False
        for line in lines:
            if not skipping and re.search(self.start_pattern, line):
                skipping = True
                continue
            if skipping:
                if re.search(self.end_pattern, line):
                    skipping = False
                continue
            result.append(line)
        path.write_text("".join(result))


@dataclass
class RemovePrecommitHooks:
    """Remove pre-commit hooks by id and clean up empty repo blocks."""

    hook_ids: list[str]

    def apply(self, file_path: Path) -> None:
        content = file_path.read_text()
        lines = content.splitlines(keepends=True)
        result: list[str] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            # Check if this line starts a hook we want to remove
            if any(f"id: {hid}" in line for hid in self.hook_ids):
                # Skip until next hook (- id:) or next repo (- repo:) or blank line after block
                i += 1
                while i < len(lines):
                    next_line = lines[i]
                    # Stop before next hook or repo definition
                    if re.match(r"^      - id:", next_line) or re.match(
                        r"^  - repo:", next_line
                    ):
                        break
                    i += 1
                    # If we hit a blank line, consume it and stop
                    if next_line.strip() == "":
                        break
                continue
            result.append(line)
            i += 1

        # Second pass: remove empty repo blocks (any repo with no remaining hooks)
        final: list[str] = []
        i = 0
        result_lines = result
        while i < len(result_lines):
            line = result_lines[i]
            if re.match(r"^  - repo:", line):
                # Buffer this repo block header
                buf = [line]
                i += 1
                while i < len(result_lines) and not re.match(
                    r"^  - repo:", result_lines[i]
                ):
                    buf.append(result_lines[i])
                    i += 1
                # Trailing comments/blanks belong to the *next* section, not this block
                tail: list[str] = []
                while len(buf) > 1 and re.match(r"^\s*#", buf[-1]):
                    tail.insert(0, buf.pop())
                while len(buf) > 1 and buf[-1].strip() == "" and tail:
                    tail.insert(0, buf.pop())
                has_hooks = any(re.match(r"^      - id:", b) for b in buf)
                if has_hooks:
                    final.extend(buf)
                elif final and final[-1].strip().startswith("#"):
                    final.pop()
                final.extend(tail)
                continue
            final.append(line)
            i += 1

        file_path.write_text("".join(final))


@dataclass
class ReplaceBlock:
    """Replace a block of lines (start through end, inclusive) with new content.

    If keep_start is True, the start line is preserved and replacement is
    inserted after it.  Otherwise the start line is also replaced.
    """

    start_pattern: str
    end_pattern: str
    replacement: str
    target: str = ""
    keep_start: bool = False

    def apply(self, file_path: Path) -> None:
        path = _resolve(file_path, self.target)
        if path is None:
            return
        content = path.read_text()
        lines = content.splitlines(keepends=True)
        result = []
        skipping = False
        replaced = False
        for line in lines:
            if not skipping and re.search(self.start_pattern, line):
                skipping = True
                if self.keep_start:
                    result.append(line)
                if not replaced:
                    result.append(self.replacement)
                    replaced = True
                continue
            if skipping:
                if re.search(self.end_pattern, line):
                    skipping = False
                continue
            result.append(line)
        path.write_text("".join(result))
