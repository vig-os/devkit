"""Validate per-worktree site bindings and run external PATH initializers.

The git toplevel (including linked worktrees) owns .site/, even when invoked
from a subdirectory. No command operates outside a git work tree.
validate_patterns(path: Path) -> None is the public S4/S6 validation boundary;
see the ADR-site-agnostic-projects S4 pattern-file clarification in Amendments.
Site-binding credential restrictions never apply to gitleaks pattern values.
"""

import argparse
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import tomllib
import unicodedata
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import unquote, urlsplit

SITE = re.compile(r"[a-z0-9][a-z0-9-]*")
CREDENTIAL = re.compile(
    r"secret|token|password|passwd|credential|private[_-]?key|access[_-]?key", re.I
)


class UsageError(ValueError):
    """An invalid invocation or reserved name (CLI exit status 2)."""

    exit_code = 2


def repository_root():
    """Resolve this worktree's git toplevel, never a cwd-based fallback."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        raise UsageError(
            "Cannot determine git work tree; git must be on PATH"
        ) from error
    if result.returncode:
        raise UsageError("Run this command inside a git work tree")
    return Path(result.stdout.rstrip("\n")).resolve()


def reject_reserved(name):
    """Reserve pattern filenames at every site-name entry point."""
    if isinstance(name, str) and name.casefold() == "leak-patterns":
        raise UsageError("Site name is reserved for leak-patterns.toml")


def read(path):
    """Read TOML without exposing configuration values in errors."""
    try:
        return tomllib.loads(path.read_text())
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ValueError(f"Cannot read TOML: {path.name}") from error


def check_credentials(value, field=""):
    """Reject credential keys and URI userinfo at every depth."""
    if isinstance(value, dict):
        for key, item in value.items():
            if CREDENTIAL.search(key):
                raise ValueError("Credential keys are forbidden")
            check_credentials(item, f"{field}.{key}" if field else key)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            check_credentials(item, f"{field}[{index}]")
    elif isinstance(value, str) and re.search(r"[A-Za-z][\w+.-]*://[^/]*@", value):
        raise ValueError(f"URI userinfo is forbidden in {field}")


def dataset_names(root):
    """Read only dataset names from the repository manifest."""
    return set(read(root / "data.toml").get("datasets", {}))


def valid_bucket(name):
    """Accept general-purpose S3 bucket names, not access-point aliases."""
    return (
        re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", name) is not None
        and ".." not in name
        and re.fullmatch(r"[0-9]+(?:\.[0-9]+){3}", name) is None
        and not name.startswith(("xn--", "sthree-", "amzn-s3-demo-"))
        and not name.endswith(("-s3alias", "--ol-s3", ".mrap", "--x-s3", "--table-s3"))
    )


def valid_uri(location):
    """Check the documented URI forms without normalizing unsafe characters."""
    uri = urlsplit(location)
    if not location.lower().startswith(uri.scheme + "://"):
        return False
    if uri.scheme == "file":
        return (
            not uri.netloc
            and uri.path.startswith("/")
            and ".." not in unquote(uri.path).split("/")
            and not uri.query
            and not uri.fragment
        )
    if uri.scheme == "s3":
        return valid_bucket(uri.netloc)
    return uri.scheme in {"gs", "az", "abfs", "http", "https"} and bool(uri.netloc)


def validate_location(location, field="location"):
    """Accept unbound, absolute paths, or s3/gs/az/abfs/http/https/file URIs.

    All forms reject whitespace, Unicode Cc controls and U+2028/U+2029 before
    parsing. file:// requires an absolute path, no authority or .. segments.
    s3:// requires a general-purpose bucket name; other URIs need authority.
    Errors name the field and never include the supplied location.
    """
    error = ValueError(
        f"Invalid {field}: expected unbound, absolute path or supported URI"
    )
    if not isinstance(location, str) or any(
        char.isspace() or unicodedata.category(char) == "Cc" or char in "\u2028\u2029"
        for char in location
    ):
        raise error
    if not location or Path(location).is_absolute():
        return
    try:
        valid = valid_uri(location)
    except ValueError:
        valid = False
    if not valid:
        raise error


def folded_keys(value, path):
    """Fold TOML keys recursively, rejecting ambiguous case variants."""
    if isinstance(value, list):
        return [folded_keys(item, path) for item in value]
    if not isinstance(value, dict):
        return value
    folded = {}
    for key, item in value.items():
        key = key.casefold()
        if key in folded:
            raise ValueError(f"{path.name}: duplicate key {key}")
        folded[key] = folded_keys(item, path)
    return folded


def validate_patterns(path: Path) -> None:
    """Validate a self-contained gitleaks TOML file; return None on success.

    Missing files mean no check. Keys are case-insensitive; duplicate case
    variants are errors. Reject extend, and require at least one usable rule:
    a nonempty string id and nonempty string regex or path. Other semantics
    belong to gitleaks. Raise ValueError with filename/key, never pattern values.
    S6 consumes this public function; the ADR Amendments define the contract.
    """
    if not path.exists():
        return
    data = folded_keys(read(path), path)
    if "extend" in data:
        raise ValueError(
            f"{path.name}: extend is forbidden; config must be self-contained"
        )
    rules = data.get("rules")
    if not isinstance(rules, list) or not any(
        isinstance(rule, dict)
        and isinstance(rule.get("id"), str)
        and rule["id"]
        and any(
            isinstance(rule.get(key), str) and rule[key] for key in ("regex", "path")
        )
        for rule in rules
    ):
        raise ValueError(f"{path.name}: no usable rules; require id and regex or path")


def validate(path, root):
    """Validate schema v1; warn on mismatches and report unbound datasets."""
    reject_reserved(path.stem)
    data = read(path)
    reject_reserved(data.get("site"))
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
    locations = {
        f"datasets.{name}.location": binding["location"]
        for name, binding in bindings.items()
    }
    if "output" in data:
        if not isinstance(data["output"], dict):
            raise ValueError("output must be a table")
        locations["output.location"] = data["output"].get("location", "")
    for field, location in locations.items():
        validate_location(location, field)
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
        reject_reserved(name)
        if not SITE.fullmatch(name) or not (directory / f"{name}.toml").is_file():
            raise ValueError("DEVKIT_SITE must name an existing .site/<site>.toml")
        return directory / f"{name}.toml"
    paths = sorted(
        p for p in directory.glob("*.toml") if p.name.casefold() != "leak-patterns.toml"
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
    reject_reserved(name)
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


def discover(root):
    """Discover external initializers; never search relative or in-tree PATHs."""
    found = {}
    for entry in os.get_exec_path():
        directory = Path(entry)
        if not directory.is_absolute() or directory.resolve().is_relative_to(root):
            continue
        for path in directory.glob("devkit-site-init-*"):
            name = path.name.removeprefix("devkit-site-init-")
            binary = path.resolve()
            if path.is_file() and os.access(path, os.X_OK):
                reject_reserved(name)
            if (
                SITE.fullmatch(name)
                and path.is_file()
                and os.access(path, os.X_OK)
                and not binary.is_relative_to(root)
            ):
                found.setdefault(name, binary)
    return found


@contextmanager
def site_directory(root):
    """Remove a newly created site directory if the run leaves it empty."""
    directory = root / ".site"
    created = not directory.exists()
    directory.mkdir(exist_ok=True)
    try:
        yield directory
    finally:
        if created and directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()


def unstaged_state(directory, stage=None):
    """Recursively snapshot paths, types, sizes, mtimes and inodes without links.

    Exclude only the active staging directory; refuse symlinks and special
    files anywhere else under .site/, including the .site/ directory itself.
    """
    state = {}
    if directory.is_symlink():
        raise ValueError("Unsupported .site entry: .site (symlink)")
    if not directory.exists():
        return state
    pending = [directory]
    while pending:
        for path in pending.pop().iterdir():
            if path == stage:
                continue
            info = path.lstat()
            name = path.relative_to(directory).as_posix()
            if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                raise ValueError(f"Unsupported .site entry: {name}")
            state[name] = (info.st_mode, info.st_size, info.st_mtime_ns, info.st_ino)
            if stat.S_ISDIR(info.st_mode):
                pending.append(path)
    return state


def publish(stage, name, root, force):
    """Validate staged outputs and all destinations before publishing any file."""
    reject_reserved(name)
    files = list(stage.iterdir())
    for path in files:
        if (
            path.is_symlink()
            or not path.is_file()
            or path.name not in (f"{name}.toml", "leak-patterns.toml")
        ):
            raise ValueError(f"Unexpected initializer output: {path.name}")
        if path.name == "leak-patterns.toml":
            validate_patterns(path)
        destination = stage.parent / path.name
        if destination.exists() and (not force or not destination.is_file()):
            raise ValueError(f"{path.name} exists; use --force to replace a file")
    validate(stage / f"{name}.toml", root)
    for path in files:
        path.replace(stage.parent / path.name)


def run_initializer(binary, name, root, stage, before):
    """Invoke the initializer, then check every entry outside its staging area."""
    env = dict(
        os.environ,
        DEVKIT_SITE=name,
        DEVKIT_SITE_DIR=str(stage),
        DEVKIT_DATA_MANIFEST=str(root / "data.toml")
        if (root / "data.toml").exists()
        else "",
    )
    result = subprocess.run([str(binary)], cwd=root, env=env, check=False)
    after = unstaged_state(stage.parent, stage)
    changed = sorted(
        key for key in before.keys() | after.keys() if before.get(key) != after.get(key)
    )
    if changed:
        print(
            "error: Initializer wrote outside staging: " + ", ".join(changed),
            file=sys.stderr,
        )
    return result.returncode or (1 if changed else 0)


def initialize(root, args):
    """Stage initializer output, detect out-of-stage writes, then publish."""
    reject_reserved(args.site)
    found = discover(root)
    name = args.site
    if name and (not SITE.fullmatch(name) or name not in found):
        raise ValueError("No initializer found for requested site")
    if not name and len(found) > 1:
        raise ValueError("Choose a site: " + ", ".join(sorted(found)))
    name = name or next(iter(found), None)
    with site_directory(root) as directory:
        before = unstaged_state(directory)
        with tempfile.TemporaryDirectory(
            prefix=".staging-", dir=directory
        ) as temporary:
            stage = Path(temporary)
            if name:
                code = run_initializer(found[name], name, root, stage, before)
                if code:
                    return code
            else:
                name = fallback(stage, root)
            publish(stage, name, root, args.force)
    print(directory / f"{name}.toml")
    return 0


def main():
    """Validate the active configuration, optionally printing its path."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print-path", action="store_true")
    args = parser.parse_args()
    try:
        root = repository_root()
        unstaged_state(root / ".site")
        path = active_site(root)
        if path:
            validate(path, root)
            if args.print_path:
                print(path)
        return 0
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return getattr(error, "exit_code", 1)


def site_init():
    """Run site initialization from the managed root recipe."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", nargs="?")
    parser.add_argument("--force", action="store_true")
    try:
        args = parser.parse_args()
        return initialize(repository_root(), args)
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return getattr(error, "exit_code", 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("site-init", "check-site-config"))
    args, remaining = parser.parse_known_args()
    sys.argv[1:] = remaining
    sys.exit(site_init() if args.command == "site-init" else main())
