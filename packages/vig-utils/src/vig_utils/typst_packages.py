"""Compose Typst registries for compilers and language servers (#1994)."""

import json
import os
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path


def data_packages(env):
    """Match Typst 0.15's platform data directory, even with a custom path."""
    home = Path(env.get("HOME", str(Path.home())))
    if sys.platform == "darwin":
        data = home / "Library/Application Support"
    elif sys.platform == "win32":
        data = Path(env.get("APPDATA", home / "AppData/Roaming"))
    else:
        data = Path(env.get("XDG_DATA_HOME") or home / ".local/share")
    return data / "typst/packages"


@contextmanager
def package_environment(env, registry=None):
    """Use consumer paths, the docs registry, then standard data-dir packages.

    First namespace/name/version wins. Resolve dependencies before this context
    ends: its package links live only for the duration of the compiler process.
    """
    paths = [Path(p) for p in env.get("TYPST_PACKAGE_PATH", "").split(os.pathsep) if p]
    if registry:
        paths.append(Path(registry))
    standard = data_packages(env)
    if standard.is_dir() and standard not in paths:
        paths.append(standard)
    if len(paths) < 2:
        yield dict(env, TYPST_PACKAGE_PATH=str(paths[0])) if paths else env
        return
    with tempfile.TemporaryDirectory(prefix="devkit-typst-packages-") as directory:
        union = Path(directory)
        for root in paths:
            if not root.is_dir():
                raise ValueError(
                    f"TYPST_PACKAGE_PATH requires existing registries: {root}"
                )
            for package in root.glob("*/*/*"):
                if package.is_dir():
                    link = union / package.relative_to(root)
                    if not link.exists():
                        link.parent.mkdir(parents=True, exist_ok=True)
                        link.symlink_to(package.resolve(), target_is_directory=True)
        yield dict(env, TYPST_PACKAGE_PATH=str(union))


def stabilize_dependencies(path):
    """Resolve input symlinks while the composed registry still exists."""
    data = json.loads(path.read_text())
    data["inputs"] = [str(Path(name).resolve()) for name in data["inputs"]]
    path.write_text(json.dumps(data) + "\n")


def main():
    """Run the supplied real tool with an additional immutable docs registry."""
    registry, tool, *args = sys.argv[1:]
    try:
        with package_environment(dict(os.environ), registry) as env:
            result = subprocess.run([tool, *args], env=env, check=False)
            # Native compile defaults to JSON. Other formats remain untouched.
            if result.returncode == 0 and "--deps" in args:
                path = args[args.index("--deps") + 1]
                if path != "-" and (
                    "--deps-format" not in args
                    or args[args.index("--deps-format") + 1] == "json"
                ):
                    stabilize_dependencies(Path(path))
        return result.returncode
    except (OSError, ValueError) as error:
        print(f"typst-with-packages: {error}", file=sys.stderr)
        return 1
