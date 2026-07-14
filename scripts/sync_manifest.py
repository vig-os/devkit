#!/usr/bin/env python3
"""Declarative workspace sync manifest.

Single source of truth for which files are copied from the repo root into
assets/workspace/ and what transformations are applied to generalize them
for downstream projects.

Usage:
    uv run python scripts/sync_manifest.py sync <dest_dir> [--project-root <root>]
    uv run python scripts/sync_manifest.py list
    uv run python scripts/sync_manifest.py list --transformed

Called by:
    - just sync-workspace       (dev-time: sync into assets/workspace/)
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

# Ensure scripts dir is on path for transforms import
sys.path.insert(0, str(Path(__file__).resolve().parent))

from transforms import (
    Banner,
    RemoveBlock,
    RemoveLines,
    RemovePrecommitHooks,
    ReplaceBlock,
    Sed,
    StripTrailingBlankLines,
    Transform,
)

# ── Manifest entry ───────────────────────────────────────────────────────────


@dataclass
class Entry:
    """A file or directory to sync from repo root to workspace template.

    Attributes:
        src: Source path relative to project root.
        dest: Destination path relative to workspace root (defaults to src).
        transforms: List of post-copy transformations to apply.
    """

    src: str
    dest: str = ""
    transforms: list[Transform] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.dest:
            self.dest = self.src

    @property
    def is_transformed(self) -> bool:
        """Whether the synced dest differs from the src.

        True for entries with manifest transforms, and for entries whose dest
        the provenance-banner pass (#1036) rewrites — derived from the same
        banner-eligibility logic (``_banner_style``), so the classification
        cannot drift from a hand-flagged copy. The image gate
        (tests/test_image.py::test_manifest_files) checksums every
        non-transformed entry against its src, so a bannered entry must never
        claim to be untransformed.
        """
        return len(self.transforms) > 0 or _entry_gets_banner(self.src, self.dest)


# ── Transform registry (type name -> constructor) ─────────────────────────────

_TRANSFORM_REGISTRY: dict[str, type] = {
    "Sed": Sed,
    "RemoveLines": RemoveLines,
    "StripTrailingBlankLines": StripTrailingBlankLines,
    "RemoveBlock": RemoveBlock,
    "RemovePrecommitHooks": RemovePrecommitHooks,
    "ReplaceBlock": ReplaceBlock,
}


def _build_transform(spec: dict) -> Transform:
    """Build a transform instance from config spec."""
    type_name = spec.pop("type")
    cls = _TRANSFORM_REGISTRY.get(type_name)
    if cls is None:
        raise ValueError(f"Unknown transform type: {type_name}")
    return cls(**spec)


def _load_manifest(manifest_path: Path) -> list[Entry]:
    """Load manifest from TOML config file."""
    with manifest_path.open("rb") as f:
        data = tomllib.load(f)
    entries: list[Entry] = []
    for raw in data.get("entries", []):
        src = raw["src"]
        dest = raw.get("dest", "")
        transforms: list[Transform] = []
        for t_spec in raw.get("transforms", []):
            # Copy spec to avoid mutating the original
            spec = dict(t_spec)
            transforms.append(_build_transform(spec))
        entries.append(Entry(src=src, dest=dest, transforms=transforms))
    return entries


# ── The manifest ─────────────────────────────────────────────────────────────

_MANIFEST_PATH = Path(__file__).resolve().parent / "manifest.toml"
MANIFEST: list[Entry] = _load_manifest(_MANIFEST_PATH)


# ── Provenance banners (issue #1036) ─────────────────────────────────────────
#
# Every comment-capable file under assets/workspace/ carries a two-line banner
# (transforms.Banner). The managed-vs-preserved variant is derived from the
# PRESERVE_FILES array in assets/init-workspace.sh — the single source of truth
# for what an upgrade overwrites — so the classification can never drift from a
# hand-typed copy. Because this runs on every `sync`, the sync-manifest
# pre-commit hook regenerates the banners and fails the commit on any
# hand-edited or missing one.

_INIT_WORKSPACE = Path("assets") / "init-workspace.sh"

# Files deliberately left un-bannered, grouped by reason. Coverage is knowingly
# partial (issue #1036); this list keeps every exclusion explicit.
_BANNER_SKIP: frozenset[str] = frozenset(
    {
        # Strict JSON — no comment syntax exists.
        "renovate.json",
        ".github/renovate-default.json",
        ".claude/worktrees.json",
        ".pymarkdown",
        # The three JSONC scaffold files (.devcontainer/devcontainer.json,
        # .vscode/settings.json, .devcontainer/workspace.code-workspace.example)
        # DO carry a `//` banner now (#1053): check-json excludes them in
        # nix/hooks.nix, so they are handled by _banner_style, not skip-listed.
        # Rendered from nix/hooks.nix and drift-gated by tests/test_flake_hooks.py;
        # a post-sync banner would have to be threaded through the Nix render.
        ".pre-commit-config.yaml",
        # Changelogs — a banner would churn every release diff; the .devcontainer
        # copy is a generated mirror of the root CHANGELOG.md.
        "CHANGELOG.md",
        ".devcontainer/CHANGELOG.md",
        # Version SSoT, rewritten in place by init-workspace.sh on every
        # (re)scaffold; a banner would be churned or duplicated by that write-back.
        ".vig-os",
        # Commit-message template: git strips `#` lines, so a banner would only
        # clutter the editor above the author's message on every commit.
        ".gitmessage",
        # No comment syntax.
        "LICENSE",
        # Nix source is outside this issue's enumerated comment-capable set;
        # flake.nix is consumer-owned/preserved and deferred to avoid nix-format
        # churn on re-sync.
        "flake.nix",
        # Personal, gitignored starter whose own header already claims (wrongly)
        # to be preserved even though it is absent from PRESERVE_FILES;
        # reclassifying it is a separate decision, so it is skipped rather than
        # handed a contradictory managed banner.
        "justfile.local",
    }
)


def load_preserve_files(script_path: Path) -> set[str]:
    """Parse the PRESERVE_FILES array from init-workspace.sh (the variant SSoT)."""
    text = script_path.read_text()
    match = re.search(r"^PRESERVE_FILES=\(\n(.*?)^\)", text, re.DOTALL | re.MULTILINE)
    if match is None:
        raise ValueError(f"PRESERVE_FILES array not found in {script_path}")
    files: set[str] = set()
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        quoted = re.match(r'"([^"]+)"', stripped)
        if quoted:
            files.add(quoted.group(1))
    return files


def _banner_style(rel_path: str) -> str | None:
    """Return the comment style ("hash" | "html") for a file, or None to skip."""
    if rel_path in _BANNER_SKIP:
        return None
    name = rel_path.rsplit("/", 1)[-1]
    if name.endswith(".md"):
        return "html"
    # JSONC scaffold files (#1053): strict-JSON files (renovate.json etc.) are
    # skip-listed above and never reach here, so any remaining .json / VS Code
    # workspace file is comment-tolerant and gets the `//` banner.
    if name.endswith((".json", ".code-workspace", ".code-workspace.example")):
        return "jsonc"
    if (
        name.endswith((".yml", ".yaml", ".toml", ".sh"))
        or name == ".yamllint"
        or name in {".gitignore", ".envrc", "CODEOWNERS"}
        or name == "justfile"
        or name.startswith("justfile.")
        or rel_path.startswith(".githooks/")
    ):
        return "hash"
    return None


def _entry_gets_banner(src: str, dest: str) -> bool:
    """Whether the banner pass rewrites this entry's synced dest (#1036).

    Drives ``Entry.is_transformed``. Directory entries are classified by
    walking the SOURCE tree (this repo's checkout, like sync's default
    project root): the entry is banner-transformed if any file it syncs
    would receive a banner at its dest-relative path.
    """
    src_path = Path(__file__).resolve().parent.parent / src
    if src_path.is_dir():
        dest_root = dest.strip("/")
        return any(
            _banner_style(f"{dest_root}/{f.relative_to(src_path).as_posix()}")
            is not None
            for f in src_path.rglob("*")
            if f.is_file()
        )
    return _banner_style(dest) is not None


def apply_banners(dest_base: Path, preserve_files: set[str]) -> None:
    """Stamp the provenance banner onto every comment-capable synced file."""
    for path in sorted(dest_base.rglob("*")):
        if not path.is_file():
            continue
        rel_path = path.relative_to(dest_base).as_posix()
        style = _banner_style(rel_path)
        if style is None:
            continue
        Banner(preserved=rel_path in preserve_files, style=style).apply(path)


# ── Sync logic ───────────────────────────────────────────────────────────────


def sync(project_root: Path, dest_base: Path) -> None:
    """Copy manifest entries from project_root into dest_base, applying transforms."""
    failed = False

    for entry in MANIFEST:
        src_path = project_root / entry.src
        dest_path = dest_base / entry.dest

        if not src_path.exists():
            print(f"  [MISSING] Source not found: {entry.src}", file=sys.stderr)
            failed = True
            continue

        if src_path.is_dir():
            # Directory: rsync-like copy (delete destination first for clean sync)
            if dest_path.exists():
                shutil.rmtree(dest_path)
            shutil.copytree(src_path, dest_path)
            label = "SYNCED" if not entry.is_transformed else "TRANSFORMED"
            print(f"  [{label}]  {entry.src} -> {entry.dest}")
        elif src_path.is_file():
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, dest_path)
            label = "SYNCED" if not entry.is_transformed else "TRANSFORMED"
            print(f"  [{label}]  {entry.src} -> {entry.dest}")
        else:
            print(
                f"  [UNKNOWN] Source is neither file nor directory: {entry.src}",
                file=sys.stderr,
            )
            failed = True
            continue

        # Apply transforms
        for transform in entry.transforms:
            transform.apply(dest_path)

    if failed:
        print("Error: Some files could not be synced", file=sys.stderr)
        sys.exit(1)

    # Stamp provenance banners over the whole tree (manifest-synced and
    # directly-authored assets alike), variant driven by PRESERVE_FILES (#1036).
    apply_banners(dest_base, load_preserve_files(project_root / _INIT_WORKSPACE))

    print("All manifest entries synced successfully.")


def list_entries(transformed_only: bool = False) -> None:
    """Print manifest entries, optionally only transformed ones."""
    for entry in MANIFEST:
        if transformed_only and not entry.is_transformed:
            continue
        marker = " [T]" if entry.is_transformed else ""
        dest = f" -> {entry.dest}" if entry.dest != entry.src else ""
        print(f"  {entry.src}{dest}{marker}")


# ── CLI ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Declarative workspace sync manifest")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # sync command
    sync_parser = subparsers.add_parser(
        "sync", help="Sync manifest entries to destination"
    )
    sync_parser.add_argument("dest", help="Destination directory")
    sync_parser.add_argument(
        "--project-root",
        default=None,
        help="Project root (default: auto-detect from script location)",
    )

    # list command
    list_parser = subparsers.add_parser("list", help="List manifest entries")
    list_parser.add_argument(
        "--transformed",
        action="store_true",
        help="Only show entries with transforms",
    )

    args = parser.parse_args()

    if args.command == "sync":
        project_root = (
            Path(args.project_root)
            if args.project_root
            else Path(__file__).resolve().parent.parent
        )
        dest = Path(args.dest)
        dest.mkdir(parents=True, exist_ok=True)
        print(f"Syncing manifest entries to {dest}...")
        sync(project_root, dest)

    elif args.command == "list":
        list_entries(transformed_only=args.transformed)


if __name__ == "__main__":
    main()
