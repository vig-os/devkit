"""Opt-in Typst guards and deterministic document builds (#1994)."""

import argparse
import fnmatch
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from vig_utils.typst_packages import package_environment, stabilize_dependencies

ENTRY_PATTERN = r"(?m)^[ \t]*//[ \t]*devkit:[ \t]*entry[ \t]*$"


def manifest_value(key):
    """Read a literal manifest value without executing shell."""
    manifest = Path(".vig-os")
    if manifest.exists():
        for line in manifest.read_text().splitlines():
            if line.startswith(key + "="):
                return " ".join(shlex.split(line.split("=", 1)[1], comments=True))
    return ""


def skip_globs():
    """Return the project's additional entry/template skip globs."""
    return [
        item.strip()
        for item in manifest_value("DEVKIT_TYPST_SKIP").split(",")
        if item.strip()
    ]


def project_font_paths():
    """Allow explicit existing font directories contained in the repository."""
    value = manifest_value("DEVKIT_TYPST_FONT_PATHS")
    paths = []
    for name in value.split(":") if value else []:
        path = Path(name.strip())
        if (
            not name.strip()
            or path.is_absolute()
            or not path.resolve().is_relative_to(Path.cwd())
            or not path.is_dir()
        ):
            raise ValueError(
                f"DEVKIT_TYPST_FONT_PATHS requires existing repo-relative directories: {name}"
            )
        paths.append(path.as_posix())
    return paths


def documents():
    """Only explicitly declared entries build; templates get a smoke compile."""
    entries, templates = [], []
    skips = skip_globs()
    seen = False
    for path in sorted(Path().rglob("*.typ")):
        seen = True
        if any(
            part.startswith(".") or part in {"generated", "parts", "node_modules"}
            for part in path.parts
        ):
            continue
        if any(fnmatch.fnmatchcase(path.as_posix(), glob) for glob in skips):
            continue
        if "templates" in path.parts:
            templates.append(path)
        elif re.search(ENTRY_PATTERN, path.read_text()):
            entries.append(path)
        elif re.search(
            r"(?m)^[ \t]*(?:#set[ \t]+page\b|#show[ \t]*:|=+[ \t]+)", path.read_text()
        ):
            print(
                f"warning: {path} looks like an entry but has no // devkit: entry marker",
                file=sys.stderr,
            )
    if seen and not entries:
        print(
            "warning: zero entries declared; add // devkit: entry to entry documents",
            file=sys.stderr,
        )
    return entries, templates


def glossary_input():
    """Transport consumer YAML across Typst's package filesystem boundary."""
    configured = manifest_value("DEVKIT_GLOSSARY")
    path = Path(configured or "glossary.yaml")
    if path.is_absolute() or not path.resolve().is_relative_to(Path.cwd()):
        raise ValueError("DEVKIT_GLOSSARY must be repository-relative")
    if not configured and not path.exists():
        return []
    return ["--input", "devkit-glossary=" + path.read_text()]


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
    for font_path in project_font_paths():
        argv += ["--font-path", font_path]
    argv += glossary_input()
    if rev is not None:
        argv += ["--input", f"rev={rev}"]
    if deps:
        argv += ["--deps", str(output.with_suffix(".deps.json"))]
    with package_environment(env) as compiler_env:
        result = subprocess.run(
            [*argv, str(path), str(output)],
            check=False,
            env=compiler_env,
            capture_output=True,
            text=True,
        )
        if deps and result.returncode == 0:
            stabilize_dependencies(output.with_suffix(".deps.json"))
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


def pinned_packages(files):
    """Reject preview references without an exact package version."""
    bad = []
    for name in files:
        for package in re.findall(r'@preview/[^\s"\']+', Path(name).read_text()):
            if not re.fullmatch(r"@preview/[a-z0-9-]+:\d+\.\d+\.\d+", package):
                bad.append(f"{name}: unpinned package {package}")
    print("\n".join(bad), end="\n" if bad else "", file=sys.stderr)
    return int(bool(bad))


def generated_pdfs():
    """Reject PDF paths under generated directories in the Git index."""
    tracked = subprocess.run(
        ["git", "ls-files", "-z"], check=True, capture_output=True
    ).stdout
    bad = [
        name
        for name in tracked.decode().split("\0")
        if Path(name).suffix.casefold() == ".pdf"
        and "generated" in [part.casefold() for part in Path(name).parts[:-1]]
    ]
    print("\n".join(bad), end="\n" if bad else "", file=sys.stderr)
    return int(bool(bad))


def toolchain_probe():
    """Report resolved binaries and their own versions, never embedded Typst's."""
    identities = {}
    for tool in ("typst", "typstyle", "tinymist"):
        binary = shutil.which(tool)
        if binary is None:
            raise ValueError(f"{tool} is not on PATH")
        path = str(Path(binary).resolve())
        output = subprocess.run(
            [binary, "--version"], check=True, capture_output=True, text=True
        ).stdout
        match = re.search(
            rf"(?m)^(?:{tool}[ \t]+|Version:[ \t]*)(\d+\.\d+\.\d+)(?:[ \t(]|$)", output
        )
        source = "output"
        if match is None:
            match = re.search(rf"/nix/store/[^/]+-{tool}-(\d+\.\d+\.\d+)(?:/|$)", path)
            source = "store-path"
        if match is None:
            raise ValueError(
                f"cannot determine {tool}'s own version from --version or its store path"
            )
        identities[tool] = {"path": path, "version": match[1], "version_source": source}
    return identities


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
            return pinned_packages(args.files)
        if args.mode == "pdf":
            return generated_pdfs()
        if args.mode == "probe":
            print(json.dumps(toolchain_probe()))
            return 0
        return compile_all(args.mode, args.deps)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"typst-guard: {error}", file=sys.stderr)
        return 1
