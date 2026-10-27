"""Validate per-clone site bindings and run PATH initializers (ADR §8–§9)."""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from urllib.parse import urlsplit

SITE = re.compile(r"[a-z0-9][a-z0-9-]*")
CREDENTIAL = re.compile(
    r"secret|token|password|passwd|credential|private[_-]?key|access[_-]?key", re.I
)


def read(path):
    """Read TOML without exposing configuration values in errors."""
    try:
        return tomllib.loads(path.read_text())
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ValueError(f"Cannot read TOML: {path.name}") from error


def check_credentials(value):
    """Reject credential keys and URI userinfo at every depth."""
    if isinstance(value, dict):
        for key, item in value.items():
            if CREDENTIAL.search(key):
                raise ValueError("Credential keys are forbidden")
            check_credentials(item)
    elif isinstance(value, list):
        for item in value:
            check_credentials(item)
    elif isinstance(value, str) and re.search(r"[A-Za-z][\w+.-]*://[^/]*@", value):
        raise ValueError("URI userinfo is forbidden")


def dataset_names(root):
    """Read only dataset names from the repository manifest."""
    return set(read(root / "data.toml").get("datasets", {}))


def validate(path, root):
    """Validate schema v1; warn on mismatches and report unbound datasets."""
    data = read(path)
    check_credentials(data)
    if type(data.get("schema")) is not int or data["schema"] != 1:
        raise ValueError("Expected schema = 1")
    if not SITE.fullmatch(path.stem) or data.get("site") != path.stem:
        raise ValueError("Site must match the filename and [a-z0-9][a-z0-9-]*")
    bindings = data.get("datasets", {})
    if not isinstance(bindings, dict):
        raise ValueError("datasets must be a table")
    unbound = []
    for name, binding in bindings.items():
        if not isinstance(binding, dict) or "location" not in binding:
            raise ValueError(f"Dataset {name} requires location")
        if binding["location"] == "":
            unbound.append(name)
    locations = list(bindings.values())
    if "output" in data:
        if not isinstance(data["output"], dict):
            raise ValueError("output must be a table")
        locations.append(data["output"])
    for binding in locations:
        location = binding.get("location", "")
        if not isinstance(location, str) or (
            location
            and not Path(location).is_absolute()
            and not urlsplit(location).scheme
        ):
            raise ValueError("Location must be unbound, a URI or an absolute path")
    hints = data.get("hints", {})
    if not isinstance(hints, dict) or any(
        not isinstance(v, str) for v in hints.values()
    ):
        raise ValueError("hints must contain string values")
    if unbound:
        print(
            "notice: unbound datasets: " + ", ".join(sorted(unbound)), file=sys.stderr
        )
    if (root / "data.toml").exists():
        names = dataset_names(root)
        for label, keys in (
            ("unknown", bindings.keys() - names),
            ("missing", names - bindings.keys()),
        ):
            if keys:
                print(
                    f"warning: {label} dataset bindings: " + ", ".join(sorted(keys)),
                    file=sys.stderr,
                )


def active_site(root):
    """Resolve the active site, excluding the leak pattern configuration."""
    directory = root / ".site"
    if "DEVKIT_SITE" in os.environ:
        name = os.environ["DEVKIT_SITE"]
        if not SITE.fullmatch(name) or not (directory / f"{name}.toml").is_file():
            raise ValueError("DEVKIT_SITE must name an existing .site/<site>.toml")
        return directory / f"{name}.toml"
    paths = sorted(
        p for p in directory.glob("*.toml") if p.name != "leak-patterns.toml"
    )
    if len(paths) > 1:
        raise ValueError(
            "Set DEVKIT_SITE; multiple sites: " + ", ".join(p.stem for p in paths)
        )
    return paths[0] if paths else None


def fallback(stage, root):
    """Create an interactive binding or a noninteractive unbound template."""
    tty = sys.stdin.isatty()
    name = (input("Site name [local]: ").strip() or "local") if tty else "local"
    if not SITE.fullmatch(name):
        raise ValueError("Invalid site name")
    lines = [
        "schema = 1",
        f"site = {json.dumps(name)}",
        "# Empty locations are unbound.",
    ]
    for dataset in sorted(dataset_names(root) if (root / "data.toml").exists() else []):
        location = input(f"Location for {dataset}: ") if tty else ""
        lines += [
            f"[datasets.{json.dumps(dataset)}]",
            f"location = {json.dumps(location)}",
        ]
    output = input("Output location: ") if tty else ""
    lines += ["[output]", f"location = {json.dumps(output)}"]
    (stage / f"{name}.toml").write_text("\n".join(lines) + "\n")
    return name


def initialize(root, args):
    """Stage initializer output, validate everything, then publish bindings."""
    found = {}
    for directory in os.get_exec_path():
        for path in Path(directory).glob("devkit-site-init-*"):
            name = path.name.removeprefix("devkit-site-init-")
            if SITE.fullmatch(name) and path.is_file() and os.access(path, os.X_OK):
                found.setdefault(name, path.resolve())
    name = args.site
    if name and (not SITE.fullmatch(name) or name not in found):
        raise ValueError("No initializer found for requested site")
    if not name and len(found) > 1:
        raise ValueError("Choose a site: " + ", ".join(sorted(found)))
    name = name or next(iter(found), None)
    directory = root / ".site"
    directory.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".staging-", dir=directory) as temporary:
        stage = Path(temporary)
        if name:
            env = dict(
                os.environ,
                DEVKIT_SITE=name,
                DEVKIT_SITE_DIR=str(stage),
                DEVKIT_DATA_MANIFEST=str(root / "data.toml")
                if (root / "data.toml").exists()
                else "",
            )
            result = subprocess.run([str(found[name])], cwd=root, env=env, check=False)
            if result.returncode:
                return result.returncode
        else:
            name = fallback(stage, root)
        validate(stage / f"{name}.toml", root)
        files = list(stage.iterdir())
        for path in files:
            if (
                path.is_symlink()
                or not path.is_file()
                or path.name not in (f"{name}.toml", "leak-patterns.toml")
            ):
                raise ValueError("Unexpected initializer output")
            check_credentials(read(path))
            if (directory / path.name).exists() and not args.force:
                raise ValueError(f"{path.name} exists; use --force to replace it")
        for path in files:
            path.replace(directory / path.name)
    print(directory / f"{name}.toml")
    return 0


def main():
    """Validate the active configuration, optionally printing its path."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print-path", action="store_true")
    args = parser.parse_args()
    try:
        path = active_site(Path.cwd())
        if path:
            validate(path, Path.cwd())
            if args.print_path:
                print(path)
        return 0
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def site_init():
    """Run site initialization from the managed root recipe."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", nargs="?")
    parser.add_argument("--force", action="store_true")
    try:
        return initialize(Path.cwd(), parser.parse_args())
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    command = sys.argv.pop(1)
    sys.exit(site_init() if command == "site-init" else main())
