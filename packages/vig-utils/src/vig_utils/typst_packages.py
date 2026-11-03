"""Compose Typst registries for compilers and language servers (#1994)."""

import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
from contextlib import contextmanager, suppress
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


def option_value(args, option, default=None):
    """Read both native long-option spellings without consuming tool arguments."""
    value = default
    for index, arg in enumerate(args):
        if arg == "--":
            break
        if arg == option and index + 1 < len(args):
            value = args[index + 1]
        elif arg.startswith(option + "="):
            value = arg.split("=", 1)[1]
    return value


def dependency_prefix(value, fmt):
    """Encode a package prefix in Typst's JSON, Make or NUL-delimited syntax."""
    if fmt == "json":
        return json.dumps(value, ensure_ascii=False)[1:-1].encode()
    if fmt == "make":
        value = "".join(
            "$$" if c == "$" else "\\" + c if c in " \t#:\\" else c for c in value
        )
    return os.fsencode(value)


def rewrite_dependencies(data, fmt, package_path):
    """Replace absolute and relative union package prefixes before cleanup.

    Prefix substitution preserves native framing, ordering, escaping and zero
    format's non-Unicode paths. Make destinations containing CR/LF or backslash
    cannot be represented safely here; preserve that artifact verbatim.
    """
    if not package_path or fmt not in {"json", "make", "zero"}:
        return data
    replacements = []
    for package in Path(package_path).glob("*/*/*"):
        if not package.is_dir():
            continue
        target = str(package.resolve()) + os.sep
        if fmt == "make" and any(c in target for c in "\r\n\\"):
            return data
        for source in (str(package) + os.sep, os.path.relpath(package) + os.sep):
            replacements.append(
                (dependency_prefix(source, fmt), dependency_prefix(target, fmt))
            )
    for source, target in sorted(
        replacements, key=lambda pair: len(pair[0]), reverse=True
    ):
        data = data.replace(source, target)
    return data


def run_tool(argv, env, capture_stdout):
    """Forward terminal signals, wait for the child and restore caller handlers."""
    with subprocess.Popen(
        argv, env=env, stdout=subprocess.PIPE if capture_stdout else None
    ) as child:

        def forward(signum, frame):
            with suppress(ProcessLookupError):
                child.send_signal(signum)

        previous = {
            s: signal.signal(s, forward)
            for s in (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
        }
        try:
            stdout, _ = child.communicate()
        finally:
            for signum, handler in previous.items():
                signal.signal(signum, handler)
        code = child.returncode
        return (128 - code if code < 0 else code), stdout


def rewrite_dependency_file(path, fmt, package_path):
    """Replace artifacts atomically; preserve compiler success on I/O failure."""
    temporary = None
    try:
        path = path.resolve()
        data = rewrite_dependencies(path.read_bytes(), fmt, package_path)
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            output.write(data)
        temporary.chmod(path.stat().st_mode & 0o777)
        temporary.replace(path)
    except OSError as error:
        print(
            f"typst-with-packages: could not stabilize {path}: {error}; artifact unchanged",
            file=sys.stderr,
        )
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    """Run the real tool, stabilizing dependency files or stdout before cleanup."""
    registry, tool, *args = sys.argv[1:]
    output = option_value(args, "--deps")
    fmt = option_value(args, "--deps-format", "json")
    try:
        with package_environment(dict(os.environ), registry) as env:
            code, stdout = run_tool([tool, *args], env, output == "-")
            if stdout is not None:
                stdout = rewrite_dependencies(
                    stdout, fmt, env.get("TYPST_PACKAGE_PATH")
                )
                sys.stdout.buffer.write(stdout)
                sys.stdout.buffer.flush()
            elif output is not None and Path(output).exists():
                rewrite_dependency_file(
                    Path(output), fmt, env.get("TYPST_PACKAGE_PATH")
                )
        return code
    except (OSError, ValueError) as error:
        print(f"typst-with-packages: {error}", file=sys.stderr)
        return 1


def package_digest(package, injected_license=False):
    """Hash sorted relative paths and bytes; only the injected root is exempt."""
    digest = hashlib.sha256()
    for path in sorted(package.rglob("*")):
        if path.is_file() and not (injected_license and path == package / "LICENSE"):
            digest.update(path.relative_to(package).as_posix().encode() + b"\0")
            digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()


def verify_registry(registry):
    """Validate local and vendored content, plus the independent release ledger."""
    lock = json.loads((registry / "devkit-docs.lock.json").read_text())
    released = json.loads((registry / "released-packages.json").read_text())
    actual = {
        p.relative_to(registry).as_posix() for p in registry.glob("*/*/*") if p.is_dir()
    }
    if not set(released) <= set(lock) or set(lock) != actual:
        raise ValueError(
            "registry versions differ from the lock or released-package ledger"
        )
    for name, expected in lock.items():
        if (
            package_digest(registry / name, name.startswith("local/devkit-docs/"))
            != expected
        ):
            raise ValueError(f"registry content differs from lock: {name}")
