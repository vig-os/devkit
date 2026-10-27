"""Scan staged changes or selected working-tree files with site-private gitleaks rules.

No pattern file means silent success. Exit codes: 0 clean, 1 findings,
2 configuration/scanner error. Scanner diagnostics are never forwarded.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def git(root: Path, *args: str) -> bytes:
    """Run git without forwarding potentially private diagnostics."""
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, check=True
    ).stdout


def pattern_file(root: Path) -> Path | None:
    """Resolve ADR §10 precedence and reject repository-owned patterns."""
    configured = os.environ.get("DEVKIT_LEAK_PATTERNS")
    path = Path(configured) if configured else root / ".site/leak-patterns.toml"
    if configured and not path.is_absolute():
        raise ValueError("DEVKIT_LEAK_PATTERNS must be absolute")
    if not configured and not path.exists() and not path.is_symlink():
        return None
    resolved = path.resolve()
    for candidate in {path.absolute(), resolved}:
        if candidate.is_relative_to(root):
            relative = candidate.relative_to(root)
            if relative.parts[0] != ".site":
                raise ValueError(
                    "pattern file must be outside the worktree or in .site/"
                )
        tracked = subprocess.run(
            [
                "git",
                "-C",
                str(candidate.parent),
                "ls-files",
                "--error-unmatch",
                "--",
                candidate.name,
            ],
            capture_output=True,
            check=False,
        )
        if tracked.returncode == 0:
            raise ValueError("pattern file must not be tracked")
    if not resolved.is_file():
        raise ValueError("pattern file is missing or unreadable")
    return resolved


def copy_inputs(root: Path, target: Path, files: list[str]) -> None:
    """Snapshot selected files, excluding site bindings and symlinks."""
    for name in files:
        source = Path(name)
        if source.is_symlink():
            continue
        source = source.resolve()
        if not source.is_relative_to(root):
            raise ValueError("input file must be inside the worktree")
        relative = source.relative_to(root)
        if relative.parts[0] in {".site", ".git"}:
            continue
        if not source.is_file():
            continue  # Deleted files and submodules have no working-tree text.
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)


def scan_command(root: Path, temporary: Path, args: argparse.Namespace):
    """Select the staged diff or a snapshot of the requested working files."""
    if not args.all_files and not args.files:
        return root, ["git", "--pre-commit", "--staged", str(root)]
    files = args.files
    if args.all_files:
        files = [
            str(root / os.fsdecode(name))
            for name in git(
                root, "ls-files", "-z", "--cached", "--others", "--exclude-standard"
            ).split(b"\0")
            if name
        ]
    tree = temporary / "tree"
    tree.mkdir()
    copy_inputs(root, tree, files)
    return tree, ["dir", str(tree)]


def publish_findings(report: Path, tree: Path) -> int:
    """Publish only the metadata permitted in public logs."""
    findings = json.loads(report.read_text())
    for finding in findings:
        path = Path(finding["File"])
        if path.is_absolute():
            path = path.relative_to(tree)
        print(
            f"{path!s}:{int(finding['StartLine'])}: {finding['RuleID']}",
            file=sys.stderr,
        )
    return int(bool(findings))


def scan(root: Path, config: Path, args: argparse.Namespace) -> int:
    """Run gitleaks without forwarding its potentially private diagnostics."""
    with tempfile.TemporaryDirectory(prefix="site-leak-check-") as directory:
        temporary = Path(directory)
        report = temporary / "report.json"
        tree, command = scan_command(root, temporary, args)
        result = subprocess.run(
            [
                args.gitleaks,
                *command,
                "--config",
                str(config),
                "--redact",
                "--no-banner",
                "--exit-code",
                "42",
                "--report-format",
                "json",
                "--report-path",
                str(report),
            ],
            cwd=root,
            capture_output=True,
            check=False,
        )
        if result.returncode not in {0, 42}:
            raise ValueError("scanner failed; check the private configuration locally")
        return publish_findings(report, tree)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all-files", action="store_true", help="scan nonignored working-tree files"
    )
    parser.add_argument("--gitleaks", default="gitleaks", help="gitleaks executable")
    parser.add_argument(
        "files", nargs="*", help="pre-commit's selected working-tree files"
    )
    args = parser.parse_args()
    try:
        try:
            root = Path(
                os.fsdecode(git(Path.cwd(), "rev-parse", "--show-toplevel")).strip()
            ).resolve()
        except subprocess.CalledProcessError, FileNotFoundError:
            # Source archives/sandbox gates have no git metadata. With no
            # site config they still satisfy the silent no-pattern contract.
            root = Path.cwd()
        config = pattern_file(root)
        if config is None:
            return 0
        return scan(root, config, args)
    except OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError:
        # Even parser/scanner errors can contain private regexes or matches.
        print(
            "site-leak-check: invalid pattern file or scan failed; check private configuration locally",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
