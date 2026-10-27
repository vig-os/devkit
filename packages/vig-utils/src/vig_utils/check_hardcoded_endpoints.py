"""Enforce ADR §10's narrow env-only runtime configuration rules.

Usage: check-hardcoded-endpoints FILE [FILE ...]
Only shell, dotenv, Python, YAML, TOML and JSON are scanned. Exit 1 means a
finding; parse failures produce a notice and use a line-by-line scan instead.
References, reserved hosts and same-line ``devkit: allow-endpoint`` pragmas
are exempt. Diagnostics never echo assigned values.
"""

import argparse
import ast
import re
import shlex
import sys
import tomllib
from pathlib import Path
from urllib.parse import urlsplit

import yaml

ENDPOINT_KEYS = {"endpoint_url", "endpoint-url", "endpointUrl"}
AWS_KEY = r"AWS_(?:ENDPOINT_URL\w*|ACCESS_KEY_ID|SECRET_ACCESS_KEY|SESSION_TOKEN)"
ASSIGNMENT = re.compile(
    rf"(?<![\w-])(?P<key>endpoint_url|endpoint-url|endpointUrl|{AWS_KEY})"
    r"[\"']?\s*(?:\]\s*)?[:=]\s*"
    r"(?P<value>\"{3}[\s\S]*?\"{3}|'{3}[\s\S]*?'{3}|\"[^\"]*\"|'[^']*'|[^\s,;}]+)"
)
REFERENCE = re.compile(r"\$(?:\w+|\{|\()|`")
RESERVED = {
    "localhost",
    "example.com",
    "example.org",
    "example.net",
    "example",
    "test",
    "invalid",
}


def file_kind(path: Path, raw: bytes) -> str | None:
    """Classify by extension, dotenv filename, or a shell shebang."""
    if path.name == ".env" or path.name.startswith(".env.") or path.suffix == ".env":
        return "dotenv"
    kinds = {
        ".py": "python",
        ".pyw": "python",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
        ".json": "json",
    }
    if path.suffix in kinds:
        return kinds[path.suffix]
    if path.suffix in {".sh", ".bash", ".zsh", ".ksh", ".bats"}:
        return "shell"
    if raw.startswith(b"#!") and re.search(
        rb"(?:[/\s])(?:sh|bash|dash|zsh|ksh|fish|csh|tcsh)(?:\s|$)", raw.splitlines()[0]
    ):
        return "shell"
    return None


def forbidden(key: str, value: str) -> bool:
    """Classify a literal without including its value in diagnostics."""
    if not value or REFERENCE.search(value):
        return False
    is_url = value.startswith(("http://", "https://"))
    if key in ENDPOINT_KEYS and not is_url:
        return False
    if is_url:
        try:
            host = (urlsplit(value).hostname or "").lower()
        except ValueError:
            host = ""
        if host in {"127.0.0.1", "::1"} or any(
            host == name or host.endswith("." + name) for name in RESERVED
        ):
            return False
    return True


def python_assignments(source: str):
    """Yield literal endpoint keyword/dict and os.environ assignments."""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.keyword) and node.arg in ENDPOINT_KEYS:
            yield node.arg, node.value
        elif isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values, strict=True):
                if (
                    isinstance(key, ast.Constant)
                    and isinstance(key.value, str)
                    and (key.value in ENDPOINT_KEYS or re.fullmatch(AWS_KEY, key.value))
                ):
                    yield key.value, value
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if (
                    isinstance(target, ast.Subscript)
                    and ast.unparse(target.value) == "os.environ"
                    and isinstance(target.slice, ast.Constant)
                    and isinstance(target.slice.value, str)
                    and re.fullmatch(AWS_KEY, target.slice.value)
                ):
                    yield target.slice.value, node.value


def structured_assignments(node):
    """Visit YAML/JSON mappings and compose-style environment list entries."""
    if isinstance(node, yaml.MappingNode):
        for key, value in node.value:
            if (
                isinstance(key, yaml.ScalarNode)
                and isinstance(value, yaml.ScalarNode)
                and (key.value in ENDPOINT_KEYS or re.fullmatch(AWS_KEY, key.value))
                and value.tag == "tag:yaml.org,2002:str"
            ):
                yield key.start_mark.line + 1, key.value, value.value
            yield from structured_assignments(value)
    elif isinstance(node, yaml.SequenceNode):
        for value in node.value:
            yield from structured_assignments(value)
    elif isinstance(node, yaml.ScalarNode):
        match = re.fullmatch(rf"({AWS_KEY})=(.*)", node.value)
        if match:
            yield node.start_mark.line + 1, match[1], match[2]


def literal_assignments(source: str):
    """Scan literal assignments, retaining positions and ignoring comments."""
    lines = source.splitlines()
    for match in ASSIGNMENT.finditer(source):
        number = source.count("\n", 0, match.start()) + 1
        if lines[number - 1].lstrip().startswith(("#", "//")):
            continue
        key, value = match.group("key", "value")
        quoted = value.startswith(('"', "'"))
        if key in ENDPOINT_KEYS and not quoted:
            continue
        if not quoted and ("(" in value or value in {"null", "None"}):
            continue
        if quoted:
            width = 3 if value.startswith(('"' * 3, "'" * 3)) else 1
            value = value[width:-width]
            if width == 3:
                value = value.removeprefix("\n")
        yield number, key, value


def shell_assignments(source: str):
    """Inspect assignment words before commands, never quoted echo arguments."""
    lexer = shlex.shlex(source, posix=True, punctuation_chars=";&|\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    assigning = True
    while True:
        number = lexer.lineno
        token = lexer.get_token()
        if token is None:
            return
        if token and all(c in ";&|\n" for c in token):
            assigning = True
        elif assigning and token == "export":
            continue
        elif assigning and re.match(r"[A-Za-z_]\w*=", token):
            key, value = token.split("=", 1)
            if key in ENDPOINT_KEYS or re.fullmatch(AWS_KEY, key):
                yield number, key, value
        else:
            assigning = False


def parsed_assignments(source: str, kind: str):
    """Select syntax-aware readers; preserve JSONC strings and line positions."""
    if kind == "python":
        for key, node in python_assignments(source):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                yield node.lineno, key, node.value
    elif kind in {"yaml", "json"}:
        if kind == "json":
            source = re.sub(
                r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/',
                lambda m: m[0] if m[0].startswith('"') else re.sub(r"[^\n]", " ", m[0]),
                source,
                flags=re.DOTALL,
            )
        list(yaml.safe_load_all(source))
        for document in yaml.compose_all(source):
            yield from structured_assignments(document)
    elif kind == "toml":
        tomllib.loads(source)
        yield from literal_assignments(source)
    else:
        yield from shell_assignments(source)


def check_file(path: Path) -> list[tuple[int, str]]:
    """Return findings; unsupported files are inert, parse failures only notify."""
    raw = path.read_bytes()
    kind = file_kind(path, raw)
    if kind is None:
        return []
    source = raw.decode("utf-8", errors="replace")
    try:
        raw.decode("utf-8")
        assignments = list(parsed_assignments(source, kind))
    except UnicodeError, SyntaxError, ValueError, yaml.YAMLError:
        print(
            f"env-only-lint: {path}: not parseable as {kind}, scanned line-by-line",
            file=sys.stderr,
        )
        assignments = [
            (number, key, value)
            for number, line in enumerate(source.splitlines(), 1)
            for _, key, value in literal_assignments(line)
        ]
    lines = source.splitlines()
    return [
        (number, key)
        for number, key, value in assignments
        if forbidden(key, value) and "devkit: allow-endpoint" not in lines[number - 1]
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args()
    failed = False
    for path in args.files:
        try:
            findings = check_file(path)
        except OSError:
            print(f"env-only-lint: {path}: cannot read input", file=sys.stderr)
            continue
        for number, key in findings:
            print(
                f"{path}:{number}: hard-coded {key}; use the environment",
                file=sys.stderr,
            )
            failed = True
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
