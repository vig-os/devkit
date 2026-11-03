"""Query compiled content with guard-only source labels; never edit consumer files."""

import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from collections import defaultdict, deque
from functools import partial
from pathlib import Path

from defusedxml.ElementTree import ParseError, parse

from vig_utils.typst_packages import package_environment

MODES = ("figure-caption", "table-header", "house-style-bypass", "figure-text-size")


def tokens(source, comments=False):
    """Keep source offsets while skipping nested comments, strings and raw text."""
    pattern = re.compile(r'//[^\n]*|/\*|"(?:\\.|[^"\\])*"|`+|[\w-]+|[^\s]', re.DOTALL)
    result, offset = [], 0
    while match := pattern.search(source, offset):
        word = match[0]
        offset = match.end()
        if word == "/*":
            depth = 1
            while depth and (comment := re.search(r"/\*|\*/", source[offset:])):
                depth += 1 if comment[0] == "/*" else -1
                offset += comment.end()
            if depth:
                offset = len(source)
        elif word.startswith("`"):
            end = source.find(word, offset)
            offset = len(source) if end < 0 else end + len(word)
        elif not word.startswith("//") or comments:
            result.append((word, match.start(), match.end()))
    return result


def delimiter_pairs(lex):
    """Match code delimiters while tolerating literal punctuation in markup."""
    pairs, stack = {}, []
    for i, (word, _, _) in enumerate(lex):
        if word in ("(", "[", "{"):
            stack.append(i)
        elif word in (")", "]", "}") and stack:
            opening = {")": "(", "]": "[", "}": "{"}[word]
            if word == ")" and lex[stack[-1]][0] != "(":
                continue
            if not any(lex[j][0] == opening for j in stack):
                continue
            while lex[stack[-1]][0] != opening:
                stack.pop()
            pairs[stack.pop()] = i
    return pairs


def in_code(i, lex, pairs, source):
    """Distinguish markup prose from hash expressions and nested code blocks."""
    if i and lex[i - 1][0] == "#":
        return True
    containers = [a for a, b in pairs.items() if a < i < b]
    if containers:
        opening = max(containers)
        if lex[opening][0] == "[":
            return False
        return in_code(opening, lex, pairs, source)
    if lex[i][0] in ("(", "{") and i:
        return in_code(i - 1, lex, pairs, source)
    line = source[source.rfind("\n", 0, lex[i][1]) + 1 : lex[i][1]]
    return bool(re.search(r"#\s*(?:let|set|show|context)\b", line))


def call_spans(source):
    """Find balanced builtin calls, including trailing content arguments."""
    lex = tokens(source)
    pairs = delimiter_pairs(lex)
    for i, (word, start, _) in enumerate(lex[:-1]):
        if word not in ("figure", "fig", "table", "image", "set"):
            continue
        if i and lex[i - 1][0] in (".", "set", "let"):
            continue
        if not in_code(i, lex, pairs, source):
            continue
        opening = i + (2 if word == "set" else 1)
        if opening not in pairs:
            continue
        end_index = pairs[opening]
        if end_index + 1 in pairs and lex[end_index + 1][0] == "[":
            end_index = pairs[end_index + 1]
        end = lex[end_index][2]
        yield (
            word,
            start,
            end,
            lex[i + 1][0],
            source[lex[opening][2] : lex[pairs[opening]][1]],
        )


def ignored(source, start, end, mode):
    """End-of-line markers apply to the opening or closing line of a call."""
    for offset in (start, end):
        line = source[
            source.rfind("\n", 0, offset) + 1 : source.find("\n", offset)
            if "\n" in source[offset:]
            else len(source)
        ]
        if any(
            re.fullmatch(rf"//\s*{mode}: ignore\s*", word)
            for word, _, _ in tokens(line, comments=True)
        ):
            return True
    return False


def instrument(source, path, origins):
    """Label queried calls in an ephemeral tree, preserving existing labels."""
    edits = []
    for kind, start, end, target, args in call_spans(source):
        line = source.count("\n", 0, start) + 1
        suppressed = {mode for mode in MODES if ignored(source, start, end, mode)}
        if kind == "set":
            if target == "page" or (
                target == "text"
                and any(
                    a[0] == "font" and b[0] == ":"
                    for a, b in zip(tokens(args), tokens(args)[1:], strict=False)
                )
            ):
                origins.setdefault("bypasses", []).append((path, line, suppressed))
            continue
        label = f"devkit-guard-{len(origins)}-{start}"
        existing = re.match(r"\s*<([\w:-]+)>", source[end:])
        if existing:
            label = existing[1]
        origins[f"<{label}>"] = (path, line, suppressed)
        prefix = "[#("
        if kind == "image":
            prefix = (
                '[#context metadata((kind: "devkit-page", id: '
                + json.dumps(f"<{label}>")
                + ", width: page.width, margin: page.margin))#("
            )
        suffix = ")]" if existing else ")#label(" + json.dumps(label) + ")]"
        edits.extend([(start, prefix), (end, suffix)])
    for offset, text in sorted(edits, reverse=True):
        source = source[:offset] + text + source[offset:]
    return source


def prepare_tree(tree, origins):
    """Mirror sources with cheap asset symlinks and instrumented Typst files."""
    shutil.copytree(
        Path.cwd(),
        tree,
        copy_function=os.symlink,
        symlinks=True,
        ignore=shutil.ignore_patterns(
            ".git", ".venv", "node_modules", "generated", ".registry"
        ),
    )
    for path in tree.rglob("*.typ"):
        name = path.relative_to(tree).as_posix()
        source = path.read_text()
        path.unlink()
        path.write_text(instrument(source, name, origins))


def run_typst(command, flags, tree, env, entry):
    """Keep document diagnostics while removing only the CLI deprecation notice."""
    result = subprocess.run(
        ["typst", *command, *flags],
        cwd=tree,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    # query's deprecation notice is not a document warning.
    diagnostics = re.sub(
        r"(?m)^warning: the `typst query` subcommand is deprecated\n = hint:.*\n?",
        "",
        result.stderr,
    )
    if result.returncode or "warning:" in diagnostics:
        raise ValueError(f"{entry}: {diagnostics.strip()}")
    return result.stdout


def query_document(entry):
    """Compile dependencies and query all guards once per entry, with two jobs."""
    from vig_utils.typst_guard import project_font_paths

    origins = {}
    env = dict(os.environ, SOURCE_DATE_EPOCH="0", TZ="UTC")
    env.pop("TYPST_FONT_PATHS", None)
    flags = [
        "--root",
        ".",
        "--ignore-system-fonts",
        "--jobs",
        "2",
        "--input",
        "devkit-guard-measure=true",
    ]
    for font in project_font_paths():
        flags += ["--font-path", str(Path(font).resolve())]
    with tempfile.TemporaryDirectory(prefix="devkit-content-") as directory:
        tree = Path(directory) / "source"
        prepare_tree(tree, origins)
        with package_environment(env) as compiler_env:
            execute = partial(
                run_typst, flags=flags, tree=tree, env=compiler_env, entry=entry
            )

            execute(["compile", str(entry), "guard.pdf", "--deps", "guard.deps.json"])
            deps = json.loads((tree / "guard.deps.json").read_text())["inputs"]
            active = set()
            for name in deps:
                p = Path(name)
                p = p if p.is_absolute() else tree / p
                if p.is_relative_to(tree):
                    active.add(p.relative_to(tree).as_posix())
            rows = json.loads(
                execute(
                    [
                        "query",
                        str(entry),
                        "selector(figure).or(table).or(image).or(metadata)",
                    ]
                )
            )
    bypasses = [row for row in origins.pop("bypasses", []) if row[0] in active]
    return rows, origins, bypasses


def blank(value):
    """Match fig(): opaque content is visible, formatting characters are blank."""
    if value is None:
        return True
    if isinstance(value, str):
        return not "".join(c for c in value if unicodedata.category(c) != "Cf").strip()
    if not isinstance(value, dict):
        return False
    if value.get("func") in ("hide", "metadata", "space", "parbreak", "linebreak"):
        return True
    for key in ("text", "child", "body"):
        if key in value:
            return blank(value[key])
    if "children" in value:
        return all(blank(child) for child in value["children"])
    return False


def points(value):
    """Convert absolute Typst lengths; unresolved relative lengths stay unknown."""
    value = re.sub(r"^0%\s*\+\s*", "", str(value))
    match = re.fullmatch(r"\s*([\d.]+)(pt|mm|cm|in|px)?\s*", value)
    return (
        float(match[1])
        * {
            None: 0.75,
            "px": 0.75,
            "pt": 1,
            "mm": 72 / 25.4,
            "cm": 720 / 25.4,
            "in": 72,
        }[match[2]]
        if match
        else None
    )


def fallback_width(image, page, intrinsic):
    """Resolve absolute/%/auto widths against page text width (never columns)."""
    text_width = 160 / 25.4 * 72
    if page and (width := points(page.get("width"))) is not None:
        margin = page.get("margin")
        if isinstance(margin, dict):
            left = points(
                margin.get("left", margin.get("x", margin.get("rest", "25mm")))
            )
            right = points(
                margin.get("right", margin.get("x", margin.get("rest", "25mm")))
            )
        else:
            left = right = points(margin)
        if left is not None and right is not None:
            text_width = width - left - right
    width = image.get("width", "auto")
    if width == "auto":
        return min(intrinsic, text_width) if intrinsic else None
    if (absolute := points(width)) is not None:
        return absolute
    match = re.fullmatch(r"([\d.]+)%\s*(?:\+\s*([\d.]+pt))?", str(width))
    return (
        float(match[1]) / 100 * text_width + (points(match[2]) if match[2] else 0)
        if match
        else None
    )


def svg_rules(root):
    """Support simple SVG CSS; report selectors requiring a full CSS engine."""
    rules = []
    for node in root.iter():
        if node.tag.split("}")[-1] == "style":
            for selectors, declarations in re.findall(
                r"([^{}]+)\{([^{}]+)\}", node.text or ""
            ):
                selectors = [selector.strip() for selector in selectors.split(",")]
                if not all(
                    re.fullmatch(r"[.#]?[\w-]+", selector) for selector in selectors
                ):
                    raise ValueError("unresolved SVG CSS selector")
                rules.append((selectors, declarations))
    return rules


def svg_font(node, inherited, rules):
    """Resolve font-size using inheritance, CSS and then inline declarations."""
    style = node.get("font-size", str(inherited))
    names = (
        node.tag.split("}")[-1],
        "#" + node.get("id", ""),
        *("." + c for c in node.get("class", "").split()),
    )
    matching = []
    for order, (selectors, declarations) in enumerate(rules):
        scores = [
            2 if selector.startswith("#") else 1 if selector.startswith(".") else 0
            for selector in selectors
            if selector in names
        ]
        if scores:
            matching.append((max(scores), order, declarations))
    for _, _, declarations in [*sorted(matching), (3, 0, node.get("style", ""))]:
        if match := re.search(r"(?:^|;)\s*font-size\s*:\s*([^;]+)", declarations):
            style = match[1].strip()
    if style in ("inherit", "unset"):
        return inherited
    if style.endswith("%"):
        return inherited * float(style[:-1]) / 100
    if style.endswith("em"):
        return inherited * float(style[:-2])
    size = points(style)
    if size is None:
        raise ValueError(f"unresolved SVG font-size {style}")
    return size / 0.75


def svg_scale(node):
    """Track scale transforms; rotations and translations preserve text size."""
    scale = 1
    for function, args in re.findall(r"(\w+)\(([^)]*)\)", node.get("transform", "")):
        if function == "scale":
            scale *= min(abs(float(n)) for n in re.split(r"[,\s]+", args.strip()))
        elif function not in ("translate", "rotate"):
            raise ValueError(f"unresolved SVG transform {function}")
    return scale


def svg_text(path):
    """Read the smallest SVG text in viewBox units and its intrinsic width."""
    root = parse(path, forbid_dtd=True).getroot()
    viewbox = root.get("viewBox", "").replace(",", " ").split()
    intrinsic = points(root.get("width", ""))
    canvas = (
        float(viewbox[2])
        if len(viewbox) == 4
        else (intrinsic / 0.75 if intrinsic else None)
    )
    rules, sizes = svg_rules(root), []

    def visit(node, inherited=16, scale=1):
        if node.get("display") == "none" or node.get("visibility") == "hidden":
            return
        size = svg_font(node, inherited, rules)
        scale *= svg_scale(node)
        if (
            node.tag.split("}")[-1] in ("text", "tspan", "textPath")
            and (node.text or "").strip()
        ):
            sizes.append(size * scale)
        for child in node:
            visit(child, size, scale)
            if (
                node.tag.split("}")[-1] in ("text", "tspan")
                and (child.tail or "").strip()
            ):
                sizes.append(size * scale)

    visit(root)
    return (
        min(sizes) if sizes else None,
        canvas,
        intrinsic or (canvas * 0.75 if canvas else None),
    )


def diagnostic(entry, origins, skips, mode, guard, label, message, warning=False):
    """Print a source diagnostic unless the selected rule is suppressed/skipped."""
    path, line, suppressed = origins.get(label, (str(entry), None, set()))
    if guard in suppressed or any(fnmatch.fnmatchcase(path, glob) for glob in skips):
        return 0
    if mode not in ("content", guard):
        return 0
    where = f"{path}:{line}" if line else path
    print(
        f"{'warning: ' if warning else ''}{where}: {guard}: {message}", file=sys.stderr
    )
    return int(not warning)


def check_svg(row, measured, pages, report):
    """Compare the smallest SVG text with the placed-size readability floor."""
    path, label = str(row.get("source", "")), row.get("label")
    if not path.casefold().endswith(".svg"):
        return 0
    try:
        smallest, canvas, intrinsic = svg_text(Path(path.lstrip("/")))
        placed = (
            points(measured[label].popleft()["width"])
            if measured[label]
            else fallback_width(
                row, pages[label].popleft() if pages[label] else None, intrinsic
            )
        )
        if placed is None or not canvas:
            return report(
                "figure-text-size",
                label,
                f"cannot resolve placed size of {path}",
                warning=True,
            )
        if smallest is not None and smallest * placed / canvas < 7:
            return report(
                "figure-text-size",
                label,
                f"{path}: smallest text is {smallest * placed / canvas:g} pt at placed width {placed:g} pt; minimum is 7 pt",
            )
    except (OSError, ValueError, ParseError) as error:
        return report(
            "figure-text-size", label, f"cannot measure {path}: {error}", warning=True
        )
    return 0


def check_entry(entry, skips, mode):
    """Combine semantic checks with source attribution and scoped suppression."""
    rows, origins, bypasses = query_document(entry)
    report = partial(diagnostic, entry, origins, skips, mode)
    failed = 0
    for path, line, suppressed in bypasses:
        origins["bypass"] = (path, line, suppressed)
        failed |= report(
            "house-style-bypass",
            "bypass",
            "use the house-style parameters instead of direct page/font settings",
        )
    values = [
        row["value"]
        for row in rows
        if row.get("func") == "metadata" and isinstance(row.get("value"), dict)
    ]
    measured, pages = defaultdict(deque), defaultdict(deque)
    for value in values:
        if value.get("kind") == "devkit-image":
            measured[value.get("label")].append(value)
        elif value.get("kind") == "devkit-page":
            pages[value.get("id")].append(value)
    for row in rows:
        kind, label = row.get("func"), row.get("label")
        if kind == "figure" and blank(row.get("caption")):
            failed |= report(
                "figure-caption", label, "figure requires a non-empty caption"
            )
        if kind == "table" and not any(
            child.get("func") == "header" for child in row.get("children", [])
        ):
            failed |= report("table-header", label, "table requires table.header")
        if kind == "image" and mode in ("content", "figure-text-size"):
            failed |= check_svg(row, measured, pages, report)
    return failed


def content_guards(mode):
    """Use the shared entry marker and skip-glob policy."""
    from vig_utils.typst_guard import documents, skip_globs

    entries, _ = documents()
    return int(sum(check_entry(entry, skip_globs(), mode) for entry in entries) > 0)
