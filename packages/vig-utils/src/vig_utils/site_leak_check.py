"""Scan staged changes or selected working-tree files with site-private gitleaks rules.

No pattern file means silent success. Exit codes: 0 clean, 1 findings,
2 configuration/scanner error. Scanner diagnostics are never forwarded.
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

from vig_utils import site_config


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
    try:
        path.lstat()
    except FileNotFoundError:
        return None
    except OSError as error:
        raise SnapshotError(
            f"unreadable pattern file {path}: {error.strerror}"
        ) from None
    resolved = path.resolve()
    for candidate in {path.absolute(), resolved}:
        if candidate.is_relative_to(root):
            relative = candidate.relative_to(root)
            if len(relative.parts) < 2 or relative.parts[0] != ".site":
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


class SnapshotError(Exception):
    """A filesystem failure containing only path metadata and an OS reason."""


def write_snapshot(target: Path, relative: Path, data: bytes, *, staged: bool) -> None:
    """Write a snapshot with a contextual, content-free filesystem error."""
    try:
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    except OSError as error:
        kind = "staged path" if staged else "input"
        raise SnapshotError(
            f"cannot materialise {kind} {relative}: {error.strerror}"
        ) from None


@contextmanager
def private_snapshot():
    """Own the snapshot and defer termination until protected deletion finishes."""
    handled = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
    received = None
    cleaning = False

    def terminate(signum, _frame):
        nonlocal received
        if received is None:
            received = signum
        if not cleaning:
            raise SystemExit(128 + received)

    previous = {signum: signal.signal(signum, terminate) for signum in handled}
    directory = None
    try:
        directory = tempfile.TemporaryDirectory(prefix="site-leak-check-")
        yield Path(directory.name)
    finally:
        cleaning = True
        mask = signal.pthread_sigmask(signal.SIG_BLOCK, handled)
        try:
            if directory is not None:
                directory.cleanup()
        finally:
            try:
                # Pending signals run our recording handler only after deletion.
                signal.pthread_sigmask(signal.SIG_SETMASK, mask)
            finally:
                for signum, handler in previous.items():
                    signal.signal(signum, handler)
        if received is not None:
            raise SystemExit(128 + received)


def copy_inputs(
    root: Path, target: Path, files: list[str], config: Path, *, text_only: bool
) -> None:
    """Snapshot files and link text, excluding active patterns and link targets."""
    for name in files:
        source = Path(os.path.normpath(Path.cwd() / name))
        is_link = source.is_symlink()
        if not is_link:
            source = source.resolve()
        if source == config:
            continue
        if not source.is_relative_to(root):
            raise ValueError("input file must be inside the worktree")
        relative = source.relative_to(root)
        if relative.parts[0] == ".git":
            continue
        if not is_link and not source.is_file():
            continue  # Deleted files and submodules have no working-tree text.
        try:
            # Path.readlink() normalizes separators and dot components.
            data = os.fsencode(os.readlink(source)) if is_link else source.read_bytes()  # noqa: PTH115
        except OSError as error:
            raise SnapshotError(
                f"cannot read input {relative}: {error.strerror}"
            ) from None
        if text_only and b"\0" in data:
            continue
        write_snapshot(target, relative, data, staged=False)


def staged_paths(root: Path) -> set[bytes]:
    """Select added, copied, modified, renamed and type-changed index paths."""
    return set(
        git(
            root,
            "diff",
            "--cached",
            "--name-only",
            "-z",
            "--diff-filter=ACMRT",
            "--no-ext-diff",
            "--no-textconv",
        ).split(b"\0")
    ) - {b""}


def index_path(name: str) -> Path:
    """Reject index paths that could escape the isolated snapshot."""
    relative = Path(name)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or not relative.parts
        or relative.parts[0] == ".git"
    ):
        raise ValueError("invalid index path")
    return relative


def read_blob(process: subprocess.Popen, oid: bytes) -> bytes:
    """Read one exact-size raw blob from the persistent cat-file batch stream."""
    process.stdin.write(oid + b"\n")
    process.stdin.flush()
    header = process.stdout.readline().split()
    if len(header) != 3 or header[:2] != [oid, b"blob"]:
        raise SnapshotError("cannot read staged blob")
    size = int(header[2])
    data = process.stdout.read(size)
    if len(data) != size or process.stdout.read(1) != b"\n":
        raise SnapshotError("cannot read staged blob")
    return data


def copy_staged_inputs(root: Path, target: Path) -> None:
    """Materialize changed index blobs through one raw cat-file batch process."""
    changed = staged_paths(root)
    if not changed:
        return
    entries = git(root, "ls-files", "--stage", "-z").split(b"\0")
    with subprocess.Popen(
        ["git", "-C", str(root), "cat-file", "--batch"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    ) as process:
        for entry in entries:
            if not entry:
                continue
            metadata, name = entry.split(b"\t", 1)
            mode, oid, stage = metadata.split()
            if (
                name not in changed
                or stage != b"0"
                or mode not in {b"100644", b"100755", b"120000"}
            ):
                continue
            relative = index_path(os.fsdecode(name))
            write_snapshot(target, relative, read_blob(process, oid), staged=True)
        process.stdin.close()
        if process.wait():
            raise SnapshotError("cannot read staged blobs")


def scan_commands(root: Path, temporary: Path, args: argparse.Namespace, config: Path):
    """Isolate scanner config without excluding repository ignore-file content."""
    tree = temporary / "tree"
    tree.mkdir()
    if not args.all_files and not args.files:
        copy_staged_inputs(root, tree)
    else:
        files = args.files
        if args.all_files:
            files = [
                str(root / os.fsdecode(name))
                for name in git(
                    root, "ls-files", "-z", "--cached", "--others", "--exclude-standard"
                ).split(b"\0")
                if name
            ]
        copy_inputs(root, tree, files, config, text_only=not args.all_files)
    # 8.30.1 also loads <source>/.gitleaksignore despite the explicit flag.
    # Scan this file separately as data, so neither pass can load it as config.
    ignore_input = tree / ".gitleaksignore"
    if ignore_input.exists():
        separate = temporary / "ignore-input"
        separate.mkdir()
        ignore_input.rename(separate / ".gitleaksignore")
        yield separate, ["dir", ".gitleaksignore"]
    yield tree, ["dir", "."]


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
    with private_snapshot() as temporary:
        report = temporary / "report.json"
        ignore = temporary / ".gitleaksignore"
        ignore.write_text("")
        failed = False
        for tree, command in scan_commands(root, temporary, args, config):
            result = subprocess.run(
                [
                    args.gitleaks,
                    *command,
                    "--config",
                    str(config),
                    "--gitleaks-ignore-path",
                    str(ignore),
                    "--redact",
                    "--no-banner",
                    "--exit-code",
                    "42",
                    "--report-format",
                    "json",
                    "--report-path",
                    str(report),
                ],
                cwd=tree,
                capture_output=True,
                check=False,
            )
            if result.returncode not in {0, 42}:
                raise ValueError(
                    "scanner failed; check the private configuration locally"
                )
            failed = bool(publish_findings(report, tree)) or failed
        return int(failed)


def parse_args() -> argparse.Namespace:
    """Parse options without allowing help-looking filenames to bypass scanning."""
    # Help-looking filenames must fail closed even outside a hook invocation.
    parser = argparse.ArgumentParser(
        description=__doc__, allow_abbrev=False, add_help=False
    )
    parser.add_argument(
        "--all-files", action="store_true", help="scan nonignored working-tree files"
    )
    parser.add_argument("--gitleaks", default="gitleaks", help="gitleaks executable")
    parser.add_argument(
        "files", nargs="*", help="pre-commit's selected working-tree files"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = None
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
        try:
            site_config.validate_patterns(config)
        except ValueError as error:
            message = (
                "unreadable pattern file"
                if isinstance(error.__cause__, OSError)
                else str(error)
            )
            print(f"site-leak-check: {config}: {message}", file=sys.stderr)
            return 2
        return scan(root, config, args)
    except SnapshotError as error:
        print(f"site-leak-check: {error}", file=sys.stderr)
        return 2
    except OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError:
        # Even parser/scanner errors can contain private regexes or matches.
        print(
            f"site-leak-check: {config or 'pattern file'}: invalid pattern file or scan failed; check private configuration locally",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
