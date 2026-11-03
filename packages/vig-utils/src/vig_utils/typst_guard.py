"""Opt-in Typst guards and deterministic document builds (#1994)."""

import argparse
import fnmatch
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path


def skip_globs():
    """Read a comma-separated literal manifest value without executing shell."""
    manifest = Path(".vig-os")
    if not manifest.exists():
        return []
    for line in manifest.read_text().splitlines():
        if line.startswith("DEVKIT_TYPST_SKIP="):
            tokens = shlex.split(line.split("=", 1)[1], comments=True)
            return [
                item.strip() for item in " ".join(tokens).split(",") if item.strip()
            ]
    return []


def documents():
    """Only explicitly declared entries build; templates get a smoke compile."""
    entries, templates = [], []
    skips = skip_globs()
    for path in sorted(Path().rglob("*.typ")):
        if any(
            part.startswith(".") or part in {"generated", "parts", "node_modules"}
            for part in path.parts
        ):
            continue
        if any(fnmatch.fnmatchcase(path.as_posix(), glob) for glob in skips):
            continue
        if "templates" in path.parts:
            templates.append(path)
        elif "// devkit: entry" in path.read_text().splitlines():
            entries.append(path)
    return entries, templates


def compile_document(path, output, rev=None, deps=False):
    """Use embedded fonts, a fixed epoch and a bounded compiler worker pool."""
    env = dict(os.environ, SOURCE_DATE_EPOCH="0", TZ="UTC")
    env.pop("TYPST_FONT_PATHS", None)
    argv = [
        "typst",
        "compile",
        "--root",
        ".",
        "--ignore-system-fonts",
        "--jobs",
        "2",
        "--diagnostic-format",
        "short",
        "--format",
        "pdf",
    ]
    if rev is not None:
        argv += ["--input", f"rev={rev}"]
    if deps:
        argv += ["--deps", str(output.with_suffix(".deps.json"))]
    result = subprocess.run(
        [*argv, str(path), str(output)], env=env, capture_output=True, text=True
    )
    sys.stderr.write(result.stderr)
    return int(result.returncode != 0 or "warning:" in result.stderr)


def compile_all(mode, deps):
    entries, templates = documents()
    rev = None
    if mode == "build":
        rev = subprocess.run(
            ["git", "rev-parse", "--short=8", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], check=True, capture_output=True, text=True
        ).stdout
        rev += "-dirty" if dirty else ""
    failed = 0
    for path in entries + templates:
        output = Path(os.devnull)
        if mode != "compile" and path in entries:
            output = path.parent / "generated" / f"{path.stem}.pdf"
            output.parent.mkdir(exist_ok=True)
        failed |= compile_document(
            path, output, rev, deps and output != Path(os.devnull)
        )
    return failed


def main(argv=None):
    """Run a guard, build entries or report toolchain identity as JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode",
        choices=["format", "compile", "pins", "pdf", "build", "canonical", "probe"],
    )
    parser.add_argument("files", nargs="*")
    parser.add_argument("--deps", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.mode == "format":
            return subprocess.run(
                ["typstyle", "--check", *args.files], check=False
            ).returncode
        if args.mode == "pins":
            bad = []
            for name in args.files:
                for package in re.findall(
                    r'@preview/[^\s"\']+', Path(name).read_text()
                ):
                    if not re.fullmatch(r"@preview/[a-z0-9-]+:\d+\.\d+\.\d+", package):
                        bad.append(f"{name}: unpinned package {package}")
            print("\n".join(bad), end="\n" if bad else "", file=sys.stderr)
            return int(bool(bad))
        if args.mode == "pdf":
            tracked = subprocess.run(
                ["git", "ls-files", "-z"], check=True, capture_output=True
            ).stdout
            bad = [
                name
                for name in tracked.decode().split("\0")
                if name.endswith(".pdf") and "generated" in Path(name).parts[:-1]
            ]
            print("\n".join(bad), end="\n" if bad else "", file=sys.stderr)
            return int(bool(bad))
        if args.mode == "probe":
            print(
                json.dumps(
                    {
                        tool: subprocess.run(
                            [tool, "--version"],
                            check=True,
                            capture_output=True,
                            text=True,
                        ).stdout.strip()
                        for tool in ["typst", "typstyle", "tinymist"]
                    }
                )
            )
            return 0
        return compile_all(args.mode, args.deps)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"typst-guard: {error}", file=sys.stderr)
        return 1
