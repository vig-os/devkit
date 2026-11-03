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
from collections import Counter, defaultdict, deque
from functools import partial
from pathlib import Path

from defusedxml.ElementTree import ParseError

from vig_utils import typst_svg
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
    if lex[i][0] == "{" and i > 2 and lex[i - 1][0] == "=":
        signature = next((a for a, b in pairs.items() if b == i - 2), None)
        if signature is not None and signature >= 2 and lex[signature - 2][0] == "let":
            return True
    if lex[i][0] in ("(", "{") and i:
        return in_code(i - 1, lex, pairs, source)
    line = source[source.rfind("\n", 0, lex[i][1]) + 1 : lex[i][1]]
    return bool(re.search(r"#\s*(?:let|set|show|context)\b", line))


def call_spans(source):
    """Find balanced builtin calls, including trailing content arguments."""
    lex = tokens(source)
    pairs = delimiter_pairs(lex)
    for i, (word, start, _) in enumerate(lex[:-1]):
        if word not in (
            "figure",
            "fig",
            "table",
            "booktabs-table",
            "plain-table",
            "image",
            "set",
        ):
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


def sets_font(args):
    """Only the top-level font argument changes the text's font family."""
    lex, depth = tokens(args), 0
    for i, (word, _, _) in enumerate(lex):
        if word in ("(", "[", "{"):
            depth += 1
        elif word in (")", "]", "}"):
            depth -= 1
        elif (
            depth == 0 and word == "font" and i + 1 < len(lex) and lex[i + 1][0] == ":"
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
            if target == "page" or (target == "text" and sets_font(args)):
                origins.setdefault("bypasses", []).append((path, line, suppressed))
            continue
        label = f"devkit-guard-{len(origins)}-{start}"
        existing = re.match(r"\s*<([^<>\s]+)>", source[end:])
        if existing:
            label = existing[1]
        origins[f"<{label}>"] = (path, line, suppressed)
        if kind == "image":
            record = {
                "id": f"<{label}>",
                "origin": (path, line, suppressed),
                "raw": None,
                "path": None,
            }
            first = tokens(args)
            if first and first[0][0].startswith('"'):
                try:
                    raw = json.loads(first[0][0])
                    canonical = (
                        raw.lstrip("/")
                        if raw.startswith("/")
                        else str(Path(path).parent / raw)
                    )
                    canonical = os.path.normpath(canonical)
                    record.update(raw=raw, path=canonical)
                    offset = source.index(args, start, end)
                    edits.extend(
                        [(offset + first[0][1], "path("), (offset + first[0][2], ")")]
                    )
                    # path() is evaluated at the original call site and retains
                    # its file identity in query JSON, without changing image's type.
                except ValueError:
                    pass
            origins.setdefault("image_calls", []).append(record)
            continue
        origins.setdefault(
            "figure_calls" if kind in ("figure", "fig") else "table_calls", []
        ).append(f"<{label}>")
        prefix = "[#("
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
    originals, written = {}, {}
    for path in tree.rglob("*.typ"):
        name = path.relative_to(tree).as_posix()
        source = path.read_text()
        path.unlink()
        originals[name] = source
        written[name] = instrument(source, name, origins)
        path.write_text(written[name])
    return originals, written


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


SIDECAR = """#show image: it => context {
  metadata((kind: "devkit-source-image", element: it,
    page: (width: page.width, height: page.height, margin: page.margin)))
  it
}
#show scale: it => context {
  metadata((kind: "devkit-transform", element: it))
  it
}
"""


def compiler_flags():
    """Use the same deterministic compiler settings as the compile guard."""
    from vig_utils.typst_guard import project_font_paths

    flags = ["--root", ".", "--ignore-system-fonts", "--jobs", "2"]
    for font in project_font_paths():
        flags += ["--font-path", str(Path(font).resolve())]
    return flags


def compile_query(entry, context, flags):
    """Keep scratch outputs outside the mirrored source/asset tree."""
    execute = partial(
        run_typst, flags=flags, tree=context["tree"], env=context["env"], entry=entry
    )
    output, deps_path = context["output"], context["deps"]
    execute(["compile", str(entry), str(output), "--deps", str(deps_path)])
    rows = json.loads(
        execute(["query", str(entry), "selector(figure).or(table).or(metadata)"])
    )
    active = set()
    for name in json.loads(deps_path.read_text())["inputs"]:
        path = Path(name)
        path = path if path.is_absolute() else context["tree"] / path
        if path.is_relative_to(context["tree"]):
            active.add(path.relative_to(context["tree"]).as_posix())
    return rows, active


def restore_sources(context, sources):
    """Switch only Typst sources; the single asset mirror stays in place."""
    for name, source in sources.items():
        (context["tree"] / name).write_text(source)


def plain_fallback(entry, context, failure):
    """Only accept fallback after the unmodified document compiles cleanly."""
    restore_sources(context, context["originals"])
    execute = partial(
        run_typst,
        flags=context["flags"],
        tree=context["tree"],
        env=context["env"],
        entry=entry,
    )
    execute(["compile", str(entry), str(context["output"])])
    print(
        f"warning: {entry}: guard instrumentation failed; using plain fallback: {failure}",
        file=sys.stderr,
    )
    path = context["tree"] / entry
    path.write_text(SIDECAR + context["originals"][str(entry)])
    try:
        return compile_query(entry, context, context["flags"])
    except ValueError as error:
        # A custom show rule can also reject the query-only sidecar. Preserve
        # the successful plain compile and retain native semantic queries.
        print(f"warning: {entry}: image metadata unavailable: {error}", file=sys.stderr)
        path.write_text(context["originals"][str(entry)])
        return compile_query(entry, context, context["flags"])


def query_document(entry, context):
    """Query one entry in the shared mirror; restore it even after a failure."""
    path = context["tree"] / entry
    path.write_text(SIDECAR + context["written"][str(entry)])
    fallback = False
    try:
        try:
            rows, active = compile_query(
                entry,
                context,
                [*context["flags"], "--input", "devkit-guard-measure=true"],
            )
        except ValueError as failure:
            fallback = True
            rows, active = plain_fallback(entry, context, failure)
    finally:
        if fallback:
            restore_sources(context, context["written"])
        else:
            path.write_text(context["written"][str(entry)])
    origins = dict(context["origins"])
    bypasses = [row for row in origins.get("bypasses", []) if row[0] in active]
    return rows, origins, bypasses, active, fallback


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


def fallback_width(image, page, intrinsic):
    """Resolve absolute/%/auto widths against page text width (never columns)."""
    text_width = 160 / 25.4 * 72
    if page and (width := typst_svg.points(page.get("width"))) is not None:
        margin = page.get("margin")
        if isinstance(margin, dict):
            left = typst_svg.points(
                margin.get("left", margin.get("x", margin.get("rest", "25mm")))
            )
            right = typst_svg.points(
                margin.get("right", margin.get("x", margin.get("rest", "25mm")))
            )
        else:
            left = right = typst_svg.points(margin)
        if left is not None and right is not None:
            text_width = width - left - right
    width = image.get("width", "auto")
    if width == "auto":
        height = typst_svg.points(image.get("height", "auto"))
        if height is not None and image.get("_intrinsic_height"):
            return min(height * intrinsic / image["_intrinsic_height"], text_width)
        return min(intrinsic, text_width) if intrinsic else None
    if (absolute := typst_svg.points(width)) is not None:
        return absolute
    match = re.fullmatch(r"([\d.]+)%\s*(?:\+\s*([\d.]+pt))?", str(width))
    return (
        float(match[1]) / 100 * text_width
        + (typst_svg.points(match[2]) if match[2] else 0)
        if match
        else None
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


def svg_text(path):
    """Keep the existing SVG inspection interface while sharing viewport logic."""
    return typst_svg.svg_text(path)


def image_path(value):
    """Decode Typst's path-valued source without losing its calling file."""
    if value.startswith("path(") and value.endswith(")"):
        value = json.loads(value[5:-1])
    return os.path.normpath(value.lstrip("/"))


def image_rows(rows, origins, active):
    """Attribute rendered images to their native source calls and page settings."""
    calls = [
        call for call in origins.get("image_calls", []) if call["origin"][0] in active
    ]
    used = defaultdict(int)
    result = []
    for row in rows:
        value = row.get("value", {}) if row.get("func") == "metadata" else {}
        if not isinstance(value, dict) or value.get("kind") != "devkit-source-image":
            continue
        element = dict(value["element"])
        source = str(element.get("source", ""))
        canonical = image_path(source)
        candidates = [call for call in calls if call["path"] == canonical]
        if not candidates:
            candidates = [
                call for call in calls if call["raw"] == source or call["raw"] is None
            ]
        if candidates:
            call = candidates[min(used[source], len(candidates) - 1)]
            used[source] += 1
            element["label"] = call["id"]
            origins[call["id"]] = call["origin"]
            if not source.startswith("path(") and not source.startswith("/"):
                canonical = os.path.normpath(
                    str(Path(call["origin"][0]).parent / source)
                )
        element["source"] = canonical
        element["_page"] = value["page"]
        element["_transformed"] = value.get("transformed", False)
        result.append(element)
    return result


def nested_images(value):
    """Find images inside native scale bodies, including figures and sequences."""
    if isinstance(value, dict):
        if value.get("func") == "image":
            yield image_path(str(value.get("source", "")))
        for child in value.values():
            yield from nested_images(child)
    elif isinstance(value, list):
        for child in value:
            yield from nested_images(child)


def query_dimensions(rows):
    """Match scale bodies to image occurrences, without tainting other uses."""
    measured, pending = defaultdict(deque), Counter()
    for row in rows:
        value = row.get("value") if row.get("func") == "metadata" else None
        if not isinstance(value, dict):
            continue
        if value.get("kind") == "devkit-image":
            measured[image_path(value["path"])].append(value)
        elif value.get("kind") == "devkit-transform":
            for path, count in Counter(nested_images(value["element"])).items():
                # Nested scales cover a subset of an outer scale's remaining
                # body; counting it twice would affect a later plain image.
                pending[path] = max(pending[path], count)
        elif value.get("kind") == "devkit-source-image":
            path = image_path(str(value["element"].get("source", "")))
            value["transformed"] = pending[path] > 0
            if pending[path]:
                pending[path] -= 1
    return measured


def check_svg(row, measured, report):
    """Use painted dimensions, including fit and SVG viewport/viewBox mapping."""
    path, label = str(row.get("source", "")), row.get("label")
    if not path.casefold().endswith(".svg"):
        return 0
    placed = measured[path].popleft() if measured[path] else None
    if row.get("_transformed"):
        return report(
            "figure-text-size",
            label,
            f"{path}: image under a scale transform; physical text size is unresolved",
            warning=True,
        )
    try:
        metrics = typst_svg.svg_metrics(Path(path))
        if placed is None:
            row["_intrinsic_height"] = metrics["height"]
            width = fallback_width(row, row.get("_page"), metrics["width"])
            height = typst_svg.points(row.get("height", "auto"))
            if height is None and width is not None:
                height = width * metrics["height"] / metrics["width"]
        else:
            width, height = (
                typst_svg.points(placed["width"]),
                typst_svg.points(placed["height"]),
            )
        if width is None or height is None:
            return report(
                "figure-text-size",
                label,
                f"cannot resolve placed size of {path}",
                warning=True,
            )
        size = typst_svg.effective_text_size(
            metrics, width, height, row.get("fit", "cover")
        )
        if size is not None and size < 7:
            return report(
                "figure-text-size",
                label,
                f"{path}: smallest text is {size:g} pt at placed size {width:g} × {height:g} pt; minimum is 7 pt",
            )
    except (OSError, ValueError, ParseError) as error:
        return report(
            "figure-text-size", label, f"cannot measure {path}: {error}", warning=True
        )
    return 0


def check_entry(entry, skips, mode, context):
    """Combine semantic checks with source attribution and scoped suppression."""
    rows, origins, bypasses, active, fallback = query_document(entry, context)
    report = partial(diagnostic, entry, origins, skips, mode)
    failed = 0
    for path, line, suppressed in bypasses:
        origins["bypass"] = (path, line, suppressed)
        failed |= report(
            "house-style-bypass",
            "bypass",
            "use the house-style parameters instead of direct page/font settings",
        )
    measured = query_dimensions(rows)
    figures = iter(origins.get("figure_calls", []))
    for row in rows:
        kind, label = row.get("func"), row.get("label")
        if fallback and kind == "figure" and label not in origins:
            label = next(figures, label)
        if kind == "figure" and blank(row.get("caption")):
            failed |= report(
                "figure-caption", label, "figure requires a non-empty caption"
            )
        # The package's show rule creates unlabelled derived tables. Only the
        # source call (including both public helpers) owns a finding/ignore.
        if (
            kind == "table"
            and label in origins
            and not any(
                child.get("func") == "header" for child in row.get("children", [])
            )
        ):
            failed |= report("table-header", label, "table requires table.header")
    if mode in ("content", "figure-text-size"):
        for row in image_rows(rows, origins, active):
            failed |= check_svg(row, measured, report)
    return failed


def content_guards(mode):
    """Build the repository mirror and package environment once per run."""
    from vig_utils.typst_guard import documents, skip_globs

    entries, _ = documents()
    if not entries:
        return 0
    env = dict(os.environ, SOURCE_DATE_EPOCH="0", TZ="UTC")
    env.pop("TYPST_FONT_PATHS", None)
    with (
        tempfile.TemporaryDirectory(prefix="devkit-content-") as directory,
        package_environment(env) as compiler_env,
    ):
        root = Path(directory)
        origins = {}
        originals, written = prepare_tree(root / "source", origins)
        context = {
            "tree": root / "source",
            "origins": origins,
            "originals": originals,
            "written": written,
            "env": compiler_env,
            "flags": compiler_flags(),
            "output": root / "guard.pdf",
            "deps": root / "guard.deps.json",
        }
        return int(
            sum(check_entry(entry, skip_globs(), mode, context) for entry in entries)
            > 0
        )
