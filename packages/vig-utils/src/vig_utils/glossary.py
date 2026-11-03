"""Validate an opt-in terminology register and scan document sources."""

import argparse
import fnmatch
import json
import re
import sys
from importlib.resources import files
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from vig_utils.typst_guard import manifest_value


def load_register():
    """Validate structure, stable IDs and Python regular expressions."""
    configured = manifest_value("DEVKIT_GLOSSARY")
    path = Path(configured or "glossary.yaml")
    if not configured and not path.exists():
        return []
    if path.is_absolute() or not path.resolve().is_relative_to(Path.cwd()):
        raise ValueError("DEVKIT_GLOSSARY must be repository-relative")
    entries = yaml.safe_load(path.read_text())
    schema = json.loads(files("vig_utils").joinpath("glossary.schema.json").read_text())
    errors = list(Draft202012Validator(schema).iter_errors(entries))
    if errors:
        raise ValueError(f"{path}: {errors[0].json_path}: {errors[0].message}")
    ids = [entry["id"] for entry in entries]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{path}: duplicate entry id")
    for entry in entries:
        if "pattern" in entry:
            re.compile(entry["pattern"])
    return entries


def boundary(pattern):
    """Match complete tokens, including punctuation inside a part number."""
    return re.compile(r"(?<!\w)(?:" + pattern + r")(?!\w)", re.IGNORECASE)


def sources():
    """Select source globs; generated and hidden directories are never scanned."""
    globs = (manifest_value("DEVKIT_GLOSSARY_SOURCES") or "*.typ,*.md").split(",")
    for path in sorted(Path().rglob("*")):
        if path.suffix not in {".typ", ".md"} or not path.is_file():
            continue
        if any(p == "generated" or p.startswith(".") for p in path.parts):
            continue
        if any(fnmatch.fnmatchcase(path.as_posix(), g.strip()) for g in globs):
            yield path


def scan(entries):
    """Report forbidden variants and unknown numbers in registered families."""
    forbidden = [
        (boundary(re.escape(item["term"])), item)
        for entry in entries
        for item in entry.get("forbidden", [])
    ]
    patterns = [boundary(e["pattern"]) for e in entries if "pattern" in e]
    known = {e["part-number"].casefold() for e in entries if "part-number" in e}
    failed = False
    for path in sources():
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if re.search(
                r"(?://\s*glossary: ignore\s*$|<!--\s*glossary: ignore\s*-->)", line
            ):
                continue
            findings = [
                f"{item['term']!r} is forbidden; use {item['use']!r}"
                for pattern, item in forbidden
                if pattern.search(line)
            ]
            findings += [
                f"unregistered part {match.group()!r}"
                for pattern in patterns
                for match in pattern.finditer(line)
                if match.group().casefold() not in known
            ]
            for finding in findings:
                print(f"{path}:{number}: {finding}", file=sys.stderr)
                failed = True
    return int(failed)


def main(argv=None):
    """Run schema validation or deterministic terminology checks."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["schema", "terms"])
    args = parser.parse_args(argv)
    try:
        entries = load_register()
        return scan(entries) if args.mode == "terms" and entries else 0
    except (OSError, ValueError, yaml.YAMLError, re.error) as error:
        print(f"glossary-guard: {error}", file=sys.stderr)
        return 1
