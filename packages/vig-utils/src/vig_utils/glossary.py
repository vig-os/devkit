"""Validate an opt-in terminology register and scan tracked document sources."""

import argparse
import json
import re
import subprocess
import sys
from bisect import bisect_right
from difflib import SequenceMatcher
from functools import cache
from importlib.resources import files
from itertools import accumulate, groupby
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


# SafeLoader's YAML 1.1 patterns miss YAML 1.2 exponent and octal scalars.
# Resolve these before schema validation so Typst and the guard agree on types.
UniqueLoader.add_implicit_resolver(
    "tag:yaml.org,2002:float",
    re.compile(r"^[-+]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)[eE][-+]?[0-9]+$"),
    list("-+0123456789."),
)
UniqueLoader.add_implicit_resolver(
    "tag:yaml.org,2002:int",
    re.compile(r"^[-+]?0o[0-7]+$"),
    list("-+0"),
)


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


def expand_source_glob(glob):
    """Expand comma alternatives before passing literal Git pathspecs."""
    match = re.search(r"\{([^{}]+)\}", glob)
    if match:
        return [
            item
            for choice in match[1].split(",")
            for item in expand_source_glob(
                glob[: match.start()] + choice + glob[match.end() :]
            )
        ]
    if "{" in glob or "}" in glob:
        raise ValueError(f"unbalanced braces in source pathspec {glob!r}")
    return [glob.strip()]


def sources(tool="glossary-guard"):
    """Use Git pathspecs; never traverse untracked, hidden or generated directories."""
    configured = manifest_value("DEVKIT_GLOSSARY_SOURCES") or "*.typ,*.md"
    globs = [
        item
        for glob in re.split(r",(?=[^{}]*(?:\{|$))", configured)
        for item in expand_source_glob(glob)
        if item
    ]
    for glob in globs:
        suffix = Path(glob).suffix
        if suffix and suffix not in SUPPRESS:
            print(f"{tool}: unsupported source suffix in {glob!r}", file=sys.stderr)
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
    forbidden, registered = [{}, {}], [set(), set()]
    exact_forbidden = {normalized(item["term"]) for item in variants}
    registered[0].update(names)
    registered[0].update(
        variant
        for name in names
        for variant in (
            name[:1].upper() + name[1:],
            " ".join(word[:1].upper() + word[1:] for word in name.split()),
        )
        if variant not in exact_forbidden
    )
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
            if not (
                (start > 0 and protected[start - 1] > start)
                or protected[start] >= end
                or protected[end - 1] > end
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


INLINE_MARKUP = re.compile(
    r"(?<!\w)#(?:strong|emph)\[([^\[\]\n]*)\](?!\w)"
    r"|(?<!\w)(\*{1,2}|_{1,2})(?=\S)([^\n]{1,1024}?)(?<=\S)\2(?!\w)"
)


def transparent_view(text, chars=None):
    """Remove simple delimiters, retaining offsets into the original source."""
    chars = list(text) if chars is None else chars
    for match in INLINE_MARKUP.finditer(text):
        start, end = match.span(1 if match[1] is not None else 3)
        for left, right in ((match.start(), start), (end, match.end())):
            for i in range(left, right):
                chars[i] = ""
    offsets = [i for i, char in enumerate(chars) if char]
    return "".join(chars), offsets


def transparent_text(text):
    """Make emphasis/code delimiters transparent for deterministic checks."""
    return transparent_view(text)[0].replace("`", " ")


COMMON_WORDS = (
    "a an the this that these those and or but nor yet so of in on for to with from "
    "is are it we you set use see read more please "
    "however when after before then also therefore meanwhile finally thus next "
    "TODO NOTE JSON YAML XML HTML HTTP HTTPS URL API MIT BSD GPL SPDX "
    "PR CI CD AM PM UTC CPU GPU RAM UTF SHA ISO ANSI RFC IEEE IEC DIN EN"
)
STOPWORDS = frozenset(COMMON_WORDS.casefold().split())
STANDARD_PREFIXES = frozenset("UTF SHA ISO ANSI RFC IEEE IEC DIN EN".casefold().split())
CONJUNCTIONS = {"and", "or", "but", "nor", "yet", "so"}
NAME_LINE = r"(?:[A-Z][a-z]+[ \t]+){1,2}[A-Z][a-z]+[ \t]*(?:\n|$)"
CANDIDATE = re.compile(
    rf"(?<![\w-])(?:[A-Z][a-z]+(?:(?:[ \t]+|[ \t]*\n(?![ \t]*{NAME_LINE})[ \t]*)[A-Z][a-z]+)+"
    r"|[A-Za-z]+-\d+[A-Za-z0-9-]*"
    r"|[A-Z]{2,}\b|[A-Za-z]+[A-Z][A-Za-z0-9]*"
    r"|[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+)(?![\w-])"
)
NOISE = [
    r"(?ms)\A---[ \t]*\n.*?^---[ \t]*(?:\n|$)",
    r"(?m)^[ \t]*(?:#{1,6}|=+)[ \t]+[^\n]*$",
    r"(?m)^[^\n]+\n[ \t]*(?:={3,}|-{3,})[ \t]*$",
    r"(?m)^[^\n]*\|[^\n]*\n[ \t]*\|?[ \t]*:?-{3,}[^\n]*$",
    r"(?ms)^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?(?:^[ \t]*\1[^\n]*(?:\n|$)|\Z)",
    r"`+[^`\n]*`+",
    r"!?\[[^\]\n]*\](?:\([^\n)]*\)|\[[^\]\n]*\])",
    r"(?m)^[ \t]*\[[^\]\n]+\]:[^\n]*$",
    URL.pattern,
    r"\[@[^\]\n]*\]|(?<!\w)@[\w:.-]+",
    r"(?<!\w)[A-Za-z]\w*_\w+(?!\w)",
    rf"(?m)^[ \t]*(?:Prepared|Reviewed|Approved|Signed|Author)(?: by)?[ \t]*:[ \t]*(?:\n[ \t]*)?{NAME_LINE}",
]


def candidate_view(text, suffix, allow=frozenset()):
    """Mask structural/code noise before stripping inline prose markup."""
    chars = list(text)
    patterns = list(NOISE)
    prefixes = "|".join(sorted(STANDARD_PREFIXES - allow))
    if prefixes:
        patterns.append(rf"(?i)\b(?:{prefixes})-\d+[A-Za-z0-9.-]*\b")
    if suffix == ".typ":
        patterns.extend([r'"(?:\\.|[^"\\])*"', r"#link\([^)]*\)\[[^\[\]]*\]"])
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            for i in range(*match.span()):
                if chars[i] not in "\r\n":
                    chars[i] = "\0"
    return transparent_view(text, chars)


def nearest_matcher(entries):
    """Cache similarity once per distinct candidate for this invocation."""
    terms = [entry["term"] for entry in entries]

    @cache
    def nearest(name):
        best = (-1.0, "")
        for term in terms:
            matcher = SequenceMatcher(None, name.casefold(), term.casefold())
            if matcher.real_quick_ratio() < best[0] or matcher.quick_ratio() < best[0]:
                continue
            best = max(best, (matcher.ratio(), term))
        return best if terms else (0.0, None)

    return nearest


def phrase_words(match, stopwords):
    """Keep joined names alongside conjunction splits, trimming edge stopwords."""
    words = list(re.finditer(r"\S+", match.group()))
    conjunctions = CONJUNCTIONS - (STOPWORDS - stopwords)
    parts = [words]
    if any(word.group().casefold() in conjunctions for word in words):
        parts.extend(
            list(group)
            for conjunction, group in groupby(
                words, lambda word: word.group().casefold() in conjunctions
            )
            if not conjunction
        )
    for words in parts:
        while words and words[0].group().casefold() in stopwords:
            words.pop(0)
        while words and words[-1].group().casefold() in stopwords:
            words.pop()
        if words:
            yield words


def candidate_names(text, known, stopwords):
    """Group prose names after subtracting known spans and trimming stopwords."""
    protected = protected_ends(
        len(text),
        (
            (s, e)
            for s, e, _ in phrase_hits(known, text_views(text)[1], overlapping=True)
        ),
    )
    groups = {}
    for match in CANDIDATE.finditer(text):
        for words in phrase_words(match, stopwords):
            name = " ".join(word.group() for word in words)
            start, end = (
                match.start() + words[0].start(),
                match.start() + words[-1].end(),
            )
            if name.casefold() in stopwords or end <= protected[start]:
                continue
            if len(words) == 1 and re.fullmatch(r"[A-Z][a-z]+", name):
                continue
            groups.setdefault(name, []).append((start, end))
    return groups


def candidate_rows(path, original, known, nearest, stopwords, allow):
    """Report locations and context from original source, never masked text."""
    text, offsets = candidate_view(original, path.suffix, allow)
    for name, positions in sorted(candidate_names(text, known, stopwords).items()):
        start, end = offsets[positions[0][0]], offsets[positions[0][1] - 1] + 1
        score, canonical = nearest(name)
        yield {
            "file": str(path),
            "line": original.count("\n", 0, start) + 1,
            "candidate": name,
            "count": len(positions),
            "nearest": canonical,
            "score": round(score, 4),
            "context": original[max(0, start - 40) : end + 40].strip(),
        }


def candidates(entries, extra_stopwords="", allow_names=""):
    """Print advisory JSON lines, continuing after individual source errors."""
    names = {
        normalized(n).casefold()
        for e in entries
        for n in [e["term"], *e.get("aliases", []), e.get("part-number", "")]
        if n
    }
    known, nearest = phrase_regex(names, overlapping=True), nearest_matcher(entries)
    allow = {word.strip().casefold() for word in allow_names.split(",")}
    stopwords = (
        STOPWORDS | {word.strip().casefold() for word in extra_stopwords.split(",")}
    ) - allow
    failed = False
    for path in sources("glossary-candidates"):
        try:
            text = read_text(path)
        except (OSError, ValueError) as error:
            print(f"glossary-candidates: {error}", file=sys.stderr)
            failed = True
            continue
        for row in candidate_rows(path, text, known, nearest, stopwords, allow):
            print(json.dumps(row, ensure_ascii=False))
    return int(failed)


def candidate_options(parser):
    """Share stoplist controls between the standalone and guard commands."""
    parser.add_argument(
        "--stopwords", default="", help="Additional comma-separated names to ignore"
    )
    parser.add_argument(
        "--allow",
        default="",
        help="Remove comma-separated names and standard prefixes from filters",
    )


def candidates_main():
    """Entry point for the standalone advisory command."""
    parser = argparse.ArgumentParser(
        description="Report unregistered terminology as advisory JSON lines."
    )
    candidate_options(parser)
    args = parser.parse_args()
    return main(["candidates", "--stopwords", args.stopwords, "--allow", args.allow])


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
    candidate_options(parser)
    args = parser.parse_args(argv)
    try:
        entries = load_register()
        if args.mode == "candidates":
            return candidates(entries, args.stopwords, args.allow)
        return scan(entries) if args.mode == "terms" and entries else 0
    except (OSError, ValueError, yaml.YAMLError, re.error) as error:
        tool = "glossary-candidates" if args.mode == "candidates" else "glossary-guard"
        print(f"{tool}: {error}", file=sys.stderr)
        return 1
