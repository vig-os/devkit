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
class ReplacePrecommitRepoBlock:
    """Replace the ``- repo:`` block defining ``hook_id`` (with the section
    comment directly above it) with ``replacement``.

    Used to decouple the scaffolded config from the repo's own: the repo runs
    pre-commit inside the Nix dev-shell, so ``ruff``/``typos`` are ``repo: local``
    / ``language: system`` hooks resolved from the flake. A downstream workspace
    commits inside the published image without that toolchain on PATH, so its
    scaffolded config must keep self-contained (pre-commit-managed) upstream
    hooks instead. Refs #697.
    """

    hook_id: str
    replacement: str

    def apply(self, file_path: Path) -> None:
        lines = file_path.read_text().splitlines(keepends=True)
        hook_idx = next(
            (
                i
                for i, ln in enumerate(lines)
                if re.match(rf"^      - id: {re.escape(self.hook_id)}\s*$", ln)
            ),
            None,
        )
        if hook_idx is None:
            return
        # Walk back to the `- repo:` line, then over its leading comment lines.
        start = hook_idx
        while start > 0 and not re.match(r"^  - repo:", lines[start]):
            start -= 1
        while start > 0 and lines[start - 1].lstrip().startswith("#"):
            start -= 1
        # End (exclusive) at the next section: a top-level comment or repo block.
        # The trailing blank separator is inside [start:end] and is replaced too,
        # so `replacement` should carry its own trailing blank line.
        end = hook_idx + 1
        while end < len(lines) and not re.match(r"^  (- repo:|#)", lines[end]):
            end += 1
        file_path.write_text("".join(lines[:start] + [self.replacement] + lines[end:]))


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
