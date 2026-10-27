"""Enforce ADR §10's narrow env-only runtime configuration rules.

Usage: check-hardcoded-endpoints FILE [FILE ...]
Exit 1 reports violations or unreadable files; exit 0 means clean input.
Python uses syntax trees so documentation strings and test fixtures stay inert.
Other text uses literal assignments (shell/dotenv, YAML, TOML and JSON).
References, local/RFC 2606 hosts, and lines carrying
``devkit: allow-endpoint`` are exempt. Broader patterns belong to site-leak-check.
Diagnostics never echo assigned values.
"""

import argparse
import ast
import re
import sys
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
REFERENCE = re.compile(r"\$(?:\w+|\{)")


def forbidden(key: str, value: str) -> bool:
    """Classify a literal without including its value in diagnostics."""
    if REFERENCE.search(value):
        return False
    is_url = value.startswith(("http://", "https://"))
    if key in ENDPOINT_KEYS and not is_url:
        return False
    if is_url:
        try:
            host = (urlsplit(value).hostname or "").lower()
        except ValueError:
            host = ""
        if host in {"localhost", "127.0.0.1", "::1", "example.com"} or host.endswith(
            (".example", ".test", ".invalid")
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
    """Visit YAML/JSON mapping keys, retaining source positions."""
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


def check_file(path: Path) -> list[tuple[int, str]]:
    """Return violating line numbers and keys; ignore binary files."""
    raw = path.read_bytes()
    if b"\0" in raw:
        return []
    source = raw.decode("utf-8")
    lines = source.splitlines()
    findings = []
    if path.suffix == ".py":
        for key, node in python_assignments(source):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and forbidden(key, node.value)
            ):
                findings.append((node.lineno, key))
    elif path.suffix in {".yaml", ".yml", ".json"}:
        if path.suffix == ".json":
            # Preserve strings and line positions while removing JSONC comments.
            source = re.sub(
                r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/',
                lambda m: m[0] if m[0].startswith('"') else re.sub(r"[^\n]", " ", m[0]),
                source,
                flags=re.DOTALL,
            )
        for document in yaml.compose_all(source):
            for number, key, value in structured_assignments(document):
                if forbidden(key, value):
                    findings.append((number, key))
    else:
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
            if forbidden(key, value):
                findings.append((number, key))
    return [
        (number, key)
        for number, key in findings
        if "devkit: allow-endpoint" not in lines[number - 1]
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args()
    failed = False
    for path in args.files:
        try:
            findings = check_file(path)
        except OSError, UnicodeError, SyntaxError, yaml.YAMLError:
            print(f"{path}: cannot read or parse input", file=sys.stderr)
            failed = True
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
