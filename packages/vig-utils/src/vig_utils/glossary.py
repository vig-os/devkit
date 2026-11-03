"""Validate an opt-in terminology register and scan tracked document sources."""

import argparse
import json
import re
import subprocess
import sys
from bisect import bisect_right
from difflib import SequenceMatcher
from importlib.resources import files
from itertools import accumulate
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from vig_utils.typst_guard import manifest_value

WORD = re.compile(r"[^\W_]")
URL = re.compile(r"(?:\b[\w+.-]+://|\bmailto:|\bwww\.)[^\s<>]+")
SUPPRESS = {
    ".typ": re.compile(r"//[ \t]*glossary: ignore[ \t]*$"),
    ".md": re.compile(r"<!--[ \t]*glossary: ignore[ \t]*-->[ \t]*$"),
}


class UniqueLoader(yaml.SafeLoader):
    """Reject duplicate mapping keys instead of silently keeping the last."""

    def construct_mapping(self, node, deep=False):
        seen = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                duplicate = key in seen
                seen.add(key)
            except TypeError as error:
                raise ValueError(
                    f"unhashable YAML key at {key_node.start_mark}"
                ) from error
            if duplicate:
                raise ValueError(f"duplicate YAML key {key!r} at {key_node.start_mark}")
        return super().construct_mapping(node, deep=deep)


def normalized(text):
    """Normalize phrase whitespace without changing punctuation or case."""
    return " ".join(text.split())


def read_text(path):
    """Name undecodable files in diagnostics, including the register itself."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeError as error:
        raise ValueError(f"{path}: not UTF-8: {error}") from error


def validate_names(entries):
    """Reject ambiguous names, cross-entry forbidden aliases and unknown replacements."""
    ids, owners, aliases, names = set(), {}, {}, set()
    for entry in entries:
        identity = entry["id"]
        if identity in ids:
            raise ValueError(f"duplicate entry id {identity!r}")
        ids.add(identity)
        for name in [entry["term"], *entry.get("aliases", [])]:
            name = normalized(name)
            if not name or owners.get(name.casefold(), identity) != identity:
                raise ValueError(
                    f"{identity}: empty or ambiguous registered name {name!r}"
                )
            owners[name.casefold()] = identity
            names.add(name)
        for alias in entry.get("aliases", []):
            aliases[normalized(alias)] = identity
    for entry in entries:
        for item in entry.get("forbidden", []):
            name = normalized(item["term"])
            if (
                not name
                or name in names
                or aliases.get(name, entry["id"]) != entry["id"]
            ):
                raise ValueError(
                    f"{entry['id']}: forbidden name {name!r} is already registered"
                )
            if normalized(item["use"]) not in names:
                raise ValueError(f"{entry['id']}: unknown replacement {item['use']!r}")


def part_patterns(entries):
    """Compile families with inline flags and known numbers scoped to identical patterns."""
    families = {}
    for entry in entries:
        if "pattern" not in entry:
            continue
        raw = entry["pattern"]
        try:
            pattern, known = families.setdefault(
                raw, (re.compile(raw, re.IGNORECASE), set())
            )
            if pattern.search("") is not None:
                raise ValueError("pattern matches empty text")
            if "part-number" in entry:
                number = entry["part-number"]
                if pattern.fullmatch(number) is None:
                    raise ValueError(f"part-number {number!r} does not match pattern")
                known.add(number.casefold())
        except (re.error, ValueError) as error:
            raise ValueError(f"{entry['id']}: {error}") from error
    return list(families.values())


def load_register():
    """Validate schema, unique YAML keys, names and every user-supplied regex."""
    configured = manifest_value("DEVKIT_GLOSSARY")
    path = Path(configured or "glossary.yaml")
    if not configured and not path.exists():
        return []
    if path.is_absolute() or not path.resolve().is_relative_to(Path.cwd()):
        raise ValueError("DEVKIT_GLOSSARY must be repository-relative")
    loader = UniqueLoader(read_text(path))
    try:
        entries = loader.get_single_data()
    finally:
        loader.dispose()
    schema = json.loads(files("vig_utils").joinpath("glossary.schema.json").read_text())
    errors = list(Draft202012Validator(schema).iter_errors(entries))
    if errors:
        raise ValueError(f"{path}: {errors[0].json_path}: {errors[0].message}")
    validate_names(entries)
    part_patterns(entries)
    return entries


def sources():
    """Use Git pathspecs; never traverse untracked, hidden or generated directories."""
    globs = (manifest_value("DEVKIT_GLOSSARY_SOURCES") or "*.typ,*.md").split(",")
    for glob in globs:
        suffix = Path(glob.strip()).suffix
        if suffix and suffix not in SUPPRESS:
            print(
                f"glossary-guard: unsupported source suffix in {glob!r}",
                file=sys.stderr,
            )
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", *[g.strip() for g in globs if g.strip()]],
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise ValueError("tracked source scanning requires a Git working tree")
    for name in result.stdout.decode(errors="surrogateescape").split("\0"):
        path = Path(name)
        if path.suffix in SUPPRESS and not any(
            p == "generated" or p.startswith(".") for p in path.parts
        ):
            yield path


def phrase_regex(names, overlapping=False):
    """One literal alternation, with flexible whitespace and prose boundaries."""
    if not names:
        return None
    patterns = [r"\s+".join(re.escape(word) for word in name.split()) for name in names]
    pattern = (
        r"(?<![^\W_])(?:"
        + "|".join(sorted(patterns, key=len, reverse=True))
        + r")(?![^\W_])"
    )
    return re.compile("(?=(" + pattern + "))" if overlapping else pattern)


def phrase_rules(entries):
    """Casing corrections are sensitive; protect registered spans before rejecting variants."""
    names = {normalized(n) for e in entries for n in [e["term"], *e.get("aliases", [])]}
    variants = [item for e in entries for item in e.get("forbidden", [])]
    folded_names = {n.casefold() for n in names}
    clashes = {normalized(item["term"]).casefold() for item in variants} & folded_names
    forbidden, registered = [{}, {}], [set(), set()]
    for name in names:
        fold = name.casefold() not in clashes
        registered[fold].add(name.casefold() if fold else name)
    for item in variants:
        name = normalized(item["term"])
        fold = name.casefold() not in folded_names
        forbidden[fold][name.casefold() if fold else name] = item
    return (
        [(phrase_regex(items, overlapping=True), items) for items in forbidden],
        [phrase_regex(items, overlapping=True) for items in registered],
    )


def text_views(text):
    """Casefold with source offsets, including expanding characters such as sharp s."""
    folded = text.casefold()
    offsets = None
    if len(folded) != len(text):
        offsets = [i for i, c in enumerate(text) for _ in c.casefold()] + [len(text)]
    return [(text, None), (folded, offsets)]


def phrase_hits(pattern, view, overlapping=False):
    """Yield source spans and normalized match keys from either text view."""
    if pattern is None:
        return
    text, offsets = view
    for match in pattern.finditer(text):
        start, end = match.span(1 if overlapping else 0)
        key = normalized(text[start:end])
        if offsets is not None:
            start, end = offsets[start], offsets[end - 1] + 1
        yield start, end, key


def protected_ends(length, spans):
    """At every offset, record the furthest end of a containing registered span."""
    ends = [0] * (length + 1)
    for start, end in spans:
        ends[start] = max(ends[start], end)
    return list(accumulate(ends, max))


def forbidden_hits(rules, registered, views):
    """Find forbidden hits outside all registered term and alias occurrences."""
    spans = (
        (s, e)
        for p, v in zip(registered, views, strict=True)
        for s, e, _ in phrase_hits(p, v, overlapping=True)
    )
    protected = protected_ends(len(views[0][0]), spans)
    hits = []
    for (pattern, items), view in zip(rules, views, strict=True):
        for start, end, key in phrase_hits(pattern, view, overlapping=True):
            if not any(
                protected[i] > i and WORD.match(views[0][0][i])
                for i in range(start, end)
            ):
                hits.append((start, end, items[key]))
    selected = []
    for start, end, item in sorted(hits, key=lambda h: (h[0] - h[1], h[0])):
        if not any(start < e and end > s for s, e in selected):
            selected.append((start, end))
            yield start, f"{item['term']!r} is forbidden; use {item['use']!r}"


def part_hits(families, text):
    """Report each unknown token once, excluding URL spans and partial tokens."""
    urls = protected_ends(len(text), (m.span() for m in URL.finditer(text)))
    seen = set()
    for pattern, known in families:
        for match in pattern.finditer(text):
            start, end = match.span()
            if (
                start == end
                or (start and WORD.match(text[start - 1]))
                or (end < len(text) and WORD.match(text[end]))
            ):
                continue
            if (
                end <= urls[start]
                or match.group().casefold() in known
                or (start, end) in seen
            ):
                continue
            seen.add((start, end))
            yield start, f"unregistered part {match.group()!r}"


def transparent_text(text):
    """Remove simple inline delimiters without changing source line numbers."""
    text = re.sub(r"#(?:strong|emph)\[([^\[\]\n]*)\]", r"\1", text)
    return re.sub(r"\*\*|__|`|\*", "", text)


STOPWORDS = frozenset(
    [
        "a",
        "an",
        "the",
        "this",
        "that",
        "these",
        "those",
        "and",
        "or",
        "of",
        "in",
        "on",
        "for",
        "to",
        "with",
        "from",
        "is",
        "are",
        "it",
        "we",
        "you",
        "set",
        "use",
        "see",
    ]
)
CANDIDATE = re.compile(
    r"(?<![\w-])(?:[A-Z][a-z]+(?:[ \t]+[A-Z][a-z]+)+"
    r"|[A-Za-z]+(?:-\d+)[A-Za-z0-9-]*"
    r"|[A-Z]{2,}\b|[A-Za-z]+[A-Z][A-Za-z0-9]*"
    r"|[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+)(?![\w-])"
)


def candidate_rows(entries, path, text):
    """Group heuristic names per file, subtracting known spans and stopwords."""
    names = {
        normalized(n)
        for e in entries
        for n in [e["term"], *e.get("aliases", []), e.get("part-number", "")]
        if n
    }
    known = phrase_regex({n.casefold() for n in names}, overlapping=True)
    protected = protected_ends(
        len(text),
        (
            (s, e)
            for s, e, _ in phrase_hits(known, text_views(text)[1], overlapping=True)
        ),
    )
    groups = {}
    for match in CANDIDATE.finditer(text):
        words = match.group().split()
        while words and words[0].casefold() in STOPWORDS:
            words.pop(0)
        name = " ".join(words)
        start = match.end() - len(name)
        if not name or name.casefold() in STOPWORDS or match.end() <= protected[start]:
            continue
        if len(words) == 1 and re.fullmatch(r"[A-Z][a-z]+", name):
            continue
        groups.setdefault(name, []).append(start)
    for name, positions in sorted(groups.items()):
        start = positions[0]
        score, nearest = max(
            (
                (SequenceMatcher(None, name.casefold(), n.casefold()).ratio(), n)
                for n in (entry["term"] for entry in entries)
            ),
            default=(0.0, None),
        )
        yield {
            "file": str(path),
            "line": text.count("\n", 0, start) + 1,
            "candidate": name,
            "count": len(positions),
            "nearest": nearest,
            "score": round(score, 4),
            "context": text[max(0, start - 40) : start + len(name) + 40].strip(),
        }


def candidates(entries):
    """Print advisory JSON lines; discoveries never fail a terminology gate."""
    for path in sources():
        for row in candidate_rows(entries, path, transparent_text(read_text(path))):
            print(json.dumps(row, ensure_ascii=False))
    return 0


def candidates_main():
    """Entry point for the standalone advisory command."""
    parser = argparse.ArgumentParser(
        description="Report unregistered terminology as advisory JSON lines."
    )
    parser.parse_args()
    return main(["candidates"])


def scan(entries):
    """Scan tracked UTF-8 sources, reporting errors without abandoning other files."""
    rules, registered = phrase_rules(entries)
    families = part_patterns(entries)
    failed = False
    for path in sources():
        try:
            text = read_text(path)
        except (OSError, ValueError) as error:
            print(
                str(error) if isinstance(error, ValueError) else f"{path}: {error}",
                file=sys.stderr,
            )
            failed = True
            continue
        text = transparent_text(text)
        text = "".join(
            "".join(c if c in "\r\n" else "\0" for c in line)
            if SUPPRESS[path.suffix].search(line.rstrip("\r\n"))
            else line
            for line in text.splitlines(keepends=True)
        )
        lines = [0, *[m.end() for m in re.finditer("\n", text)]]
        findings = [
            *forbidden_hits(rules, registered, text_views(text)),
            *part_hits(families, text),
        ]
        for start, finding in sorted(findings):
            print(f"{path}:{bisect_right(lines, start)}: {finding}", file=sys.stderr)
            failed = True
    return int(failed)


def main(argv=None):
    """Run schema validation or deterministic terminology checks."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["schema", "terms", "candidates"])
    args = parser.parse_args(argv)
    try:
        entries = load_register()
        if args.mode == "candidates":
            return candidates(entries)
        return scan(entries) if args.mode == "terms" and entries else 0
    except (OSError, ValueError, yaml.YAMLError, re.error) as error:
        print(f"glossary-guard: {error}", file=sys.stderr)
        return 1
