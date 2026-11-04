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
from bisect import bisect_right
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
            while depth and (comment := re.compile(r"/\*|\*/").search(source, offset)):
                depth += 1 if comment[0] == "/*" else -1
                offset = comment.end()
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
    pairs, stack, counts = {}, [], Counter()
    for i, (word, _, _) in enumerate(lex):
        if word in ("(", "[", "{"):
            stack.append(i)
            counts[word] += 1
        elif word in (")", "]", "}") and stack:
            opening = {")": "(", "]": "[", "}": "{"}[word]
            if word == ")" and lex[stack[-1]][0] != "(":
                continue
            if not counts[opening]:
                continue
            while lex[stack[-1]][0] != opening:
                counts[lex[stack.pop()][0]] -= 1
            counts[opening] -= 1
            pairs[stack.pop()] = i
    return pairs


def code_contexts(lex, pairs, source):
    """Compute code/markup context once, including multiline closure bodies."""
    flags, stack = [], []
    line_code, previous_end = False, 0
    for i, (word, start, end) in enumerate(lex):
        if "\n" in source[previous_end:start]:
            line_code = False
        previous_end = end
        if word == "#":
            line_code = True
        code = flags[stack[-1]] if stack else line_code
        if stack and lex[stack[-1]][0] == "[":
            code = line_code
        if i and lex[i - 1][0] == "#":
            code = True
        if word == "{" and i >= 3 and lex[i - 1][0] == ">" and lex[i - 2][0] == "=":
            code = flags[i - 3]
        if word == "{" and i >= 2 and lex[i - 1][0] == "=":
            code = code or flags[i - 2]
        flags.append(code)
        if i in pairs:
            stack.append(i)
        while stack and pairs[stack[-1]] == i:
            stack.pop()
    return flags


def call_spans(source):
    """Find balanced builtin calls, including trailing content arguments."""
    lex = tokens(source)
    pairs = delimiter_pairs(lex)
    code = code_contexts(lex, pairs, source)
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
        if not code[i]:
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


def source_index(source):
    """Index line ends and suppression comments once per source."""
    ends = [match.start() for match in re.finditer("\n", source)]
    markers = defaultdict(set)
    for word, start, _ in tokens(source, comments=True):
        match = re.fullmatch(r"//\s*([\w-]+): ignore\s*", word)
        if match and match[1] in MODES:
            markers[bisect_right(ends, start) + 1].add(match[1])
    return ends, markers


def image_origin(args, path):
    """Recognize literal strings and path values; retain dynamic source calls."""
    first = tokens(args)
    index = 2 if len(first) > 2 and first[0][0] == "path" else 0
    if len(first) <= index or not first[index][0].startswith('"'):
        return None, None
    try:
        raw = json.loads(first[index][0])
        canonical = (
            raw.lstrip("/") if raw.startswith("/") else str(Path(path).parent / raw)
        )
        return raw, os.path.normpath(canonical)
    except ValueError:
        return None, None


def image_edits(source, start, end, args):
    """Resolve strings at the calling file, preserving native image values/bytes."""
    first = tokens(args)
    if not first:
        return []
    # The first positional argument ends at a top-level comma.
    depth, last = 0, len(args)
    for word, offset, _ in first:
        if word in ("(", "[", "{"):
            depth += 1
        elif word in (")", "]", "}"):
            depth -= 1
        elif word == "," and depth == 0:
            last = offset
            break
    offset = source.index(args, start, end)
    prefix = "(value => if type(value) == str { path(value) } else { value })("
    return [(offset, prefix), (offset + last, ")")]


def logo_calls(source, path, origins, ends, markers):
    """Attribute the package's logo to the template argument that supplies it."""
    lex = tokens(source)
    for i, (word, start, _) in enumerate(lex[:-2]):
        if word != "logo" or lex[i + 1][0] != ":":
            continue
        line = bisect_right(ends, start) + 1
        last = min(i + 6, len(lex) - 1)
        raw, canonical = image_origin(source[lex[i + 2][1] : lex[last][2]], path)
        if canonical is None:
            continue
        key = f"<devkit-logo-{path}-{start}>"
        origin = (path, line, markers[line])
        origins[key] = origin
        origins.setdefault("offsets", {})[key] = start
        origins.setdefault("image_order", []).append(key)
        origins.setdefault("image_calls", []).append(
            {"id": key, "origin": origin, "raw": raw, "path": canonical, "logo": True}
        )


def instrument(source, path, origins):
    """Instrument only active sources, with unique identities per call site."""
    edits = defaultdict(list)
    ends, markers = source_index(source)
    for kind, start, end, target, args in call_spans(source):
        line = bisect_right(ends, start) + 1
        suppressed = markers[line] | markers[bisect_right(ends, end) + 1]
        if kind == "set":
            if target == "page" or (target == "text" and sets_font(args)):
                origins.setdefault("bypasses", []).append((path, line, suppressed))
            continue
        key = f"<devkit-guard-{len(origins)}-{start}>"
        origins[key] = (path, line, suppressed)
        origins.setdefault("offsets", {})[key] = start
        origins.setdefault("call_order", []).append(key)
        existing = re.compile(r"\s*<([^<>\s]+)>").match(source, end)
        label = f"<{existing[1]}>" if existing else key
        if existing:
            origins.setdefault(label, origins[key])
        origins.setdefault("label_calls", {}).setdefault(label, []).append(key)
        if kind == "image":
            raw, canonical = image_origin(args, path)
            origins.setdefault("image_order", []).append(key)
            origins.setdefault("image_calls", []).append(
                {"id": key, "origin": origins[key], "raw": raw, "path": canonical}
            )
            for offset, text in image_edits(source, start, end, args):
                edits[offset].append(text)
            continue
        origins.setdefault(
            "figure_calls" if kind in ("figure", "fig") else "table_calls", []
        ).append(key)
        edits[start].append("[#(")
        edits[end].append(
            ")]" if existing else ")#label(" + json.dumps(key[1:-1]) + ")]"
        )
    logo_calls(source, path, origins, ends, markers)
    return "".join(
        "".join(edits.get(i, ())) + char for i, char in enumerate(source + "\0")
    )[:-1]


def prepare_tree(tree, origins):
    """Mirror assets once; source instrumentation waits for compiler dependencies."""
    shutil.copytree(
        Path.cwd(),
        tree,
        copy_function=lambda source, target: (
            shutil.copyfile(source, target)
            if str(source).endswith(".typ")
            else Path(target).symlink_to(source)
        ),
        symlinks=True,
        ignore=shutil.ignore_patterns(".git", ".venv", "node_modules", ".registry"),
    )
    return {}, {}


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


SIDECAR = """#show image: it => layout(size => context {
  let placed = measure(it, width: size.width, height: size.height)
  metadata((kind: "devkit-source-image", element: it,
    width: placed.width, height: placed.height, location: here().position(),
    page: (width: page.width, height: page.height, margin: page.margin)))
  it
})
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
    return rows, dependency_paths(context)


def dependency_paths(context):
    """Normalize compiler dependency identities against the mirror root."""
    active = set()
    for name in json.loads(context["deps"].read_text())["inputs"]:
        path = Path(name)
        path = path if path.is_absolute() else context["tree"] / path
        if path.is_relative_to(context["tree"]):
            active.add(path.relative_to(context["tree"]).as_posix())
    return active


def entry_sources(entry, context):
    """Discover dependencies from an unmodified compile before scanning sources."""
    restore_sources(context, context["originals"])
    run_typst(
        ["compile", str(entry), str(context["output"]), "--deps", str(context["deps"])],
        context["flags"],
        context["tree"],
        context["env"],
        entry,
    )
    active = dependency_paths(context)
    for name in sorted(active):
        if not name.endswith(".typ") or name in context["written"]:
            continue
        path = context["tree"] / name
        source = path.read_text()
        path.unlink()
        context["originals"][name] = source
        context["written"][name] = instrument(source, name, context["origins"])
    restore_sources(context, context["written"])
    return active


def ordered_calls(entry, context, active, kind):
    """Flatten local imports/includes at their document position, ignoring inactive files."""
    calls, seen = context["origins"].get(kind, []), set()
    by_file = defaultdict(list)
    for key in calls:
        by_file[context["origins"][key][0]].append(key)

    def visit(name):
        if name in seen or name not in active:
            return []
        seen.add(name)
        source = context["originals"].get(name, "")
        events = [
            (context["origins"]["offsets"][key], key, None) for key in by_file[name]
        ]
        lex = tokens(source)
        for i, (word, start, _) in enumerate(lex[:-1]):
            if word not in ("import", "include") or not lex[i + 1][0].startswith('"'):
                continue
            raw = json.loads(lex[i + 1][0])
            target = os.path.normpath(
                raw.lstrip("/") if raw.startswith("/") else str(Path(name).parent / raw)
            )
            events.append((start, "", target))
        result = []
        for _, key, target in sorted(events):
            result.extend(visit(target) if target else [key])
        return result

    result = visit(str(entry))
    included = set(result)
    return result + [
        key
        for key in calls
        if context["origins"][key][0] in active and key not in included
    ]


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
    entry_sources(entry, context)
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
    origins = active_origins(entry, context, active)
    bypasses = [row for row in origins.get("bypasses", []) if row[0] in active]
    return rows, origins, bypasses, active, fallback


def active_origins(entry, context, active):
    """Keep call identities and label aliases local to one entry's dependencies."""
    origins = {
        key: value
        for key, value in context["origins"].items()
        if not isinstance(value, tuple) or value[0] in active
    }
    origins["figure_calls"] = ordered_calls(entry, context, active, "figure_calls")
    images = {call["id"]: call for call in origins.get("image_calls", [])}
    origins["image_calls"] = [
        images[key] for key in ordered_calls(entry, context, active, "image_order")
    ]
    order = {
        key: index
        for index, key in enumerate(ordered_calls(entry, context, active, "call_order"))
    }
    labels = {}
    for label, keys in origins.get("label_calls", {}).items():
        keys = sorted((key for key in keys if key in order), key=order.get)
        if keys:
            labels[label] = keys
            origins[label] = origins[keys[0]]
    origins["label_calls"] = labels
    return origins


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


def image_rows(rows, origins, active, package=False):
    """Attribute rendered images to their native source calls and page settings."""
    calls = [
        call for call in origins.get("image_calls", []) if call["origin"][0] in active
    ]
    calls.sort(key=lambda call: not call.get("logo", False))
    by_path, by_raw, dynamic = defaultdict(list), defaultdict(list), defaultdict(list)
    for call in calls:
        if call["path"] is not None:
            by_path[call["path"]].append(call)
        if call["raw"] is not None:
            by_raw[call["raw"]].append(call)
        else:
            dynamic[str(Path(call["origin"][0]).parent)].append(call)
    used = defaultdict(int)
    result = []
    for row in rows:
        value = row.get("value", {}) if row.get("func") == "metadata" else {}
        if not isinstance(value, dict) or value.get("kind") != "devkit-source-image":
            continue
        element = dict(value["element"])
        source = str(element.get("source", ""))
        canonical = image_path(source)
        candidates = (
            by_path[canonical] or by_raw[source] or dynamic[str(Path(canonical).parent)]
        )
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
        element["_placed"] = (
            value
            if "width" in value and (package or (candidates and call.get("logo")))
            else None
        )
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
    queued = measured[path].popleft() if measured[path] else None
    placed = row.get("_placed") or queued
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
    labels = {
        label: deque(keys) for label, keys in origins.get("label_calls", {}).items()
    }
    for row in rows:
        kind, label = row.get("func"), row.get("label")
        if kind == "figure":
            source_key = next(figures, label)
            if fallback and label not in labels:
                label = source_key
        if labels.get(label):
            label = labels[label].popleft()
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
        for row in image_rows(rows, origins, active, package=bool(measured)):
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
