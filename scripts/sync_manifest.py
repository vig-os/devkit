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
import shutil
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

# Ensure scripts dir is on path for transforms import
sys.path.insert(0, str(Path(__file__).resolve().parent))

from transforms import (
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
        return len(self.transforms) > 0


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
