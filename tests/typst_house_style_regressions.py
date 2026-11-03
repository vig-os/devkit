"""Round-two layout regressions, executed with real tools in the Nix sandbox."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

registry = Path(sys.argv[1])
version = max(
    (p.name for p in (registry / "local/devkit-docs").iterdir()),
    key=lambda v: tuple(map(int, v.split("."))),
)
prefix = f'// devkit: entry\n#import "@local/devkit-docs:{version}": *\n#show: devkit-document.with()\n'
failures = []


def run(*args):
    result = subprocess.run(args, check=False, capture_output=True, text=True)
    assert result.returncode == 0 and "warning:" not in result.stderr, (
        result.stdout + result.stderr
    )
    return result.stdout


def build(source):
    Path("main.typ").write_text(prefix + source)
    run("typst-guard", "compile")
    run("typst", "compile", "main.typ", "main.pdf")
    return run("pdftotext", "-layout", "main.pdf", "-")


def positions():
    root = ET.fromstring(run("pdftotext", "-bbox", "main.pdf", "-"))
    return {
        word.text: {key: float(value) for key, value in word.attrib.items()}
        for word in root.iter()
        if word.tag.endswith("word")
    }


def spans(cell, expected):
    build(
        "#table(columns: 3, table.cell("
        + cell
        + ")[Wide], [a], [b], [c], [d], [e], [f], [g])"
    )
    words = positions()
    for row in expected:
        assert len({round(words[word]["yMin"], 2) for word in row}) == 1, (cell, words)


def long_figure():
    text = build(
        "#fig(table(columns: 2, table.header([Repeatmarker], [Value]), ..range(120).map(n => ([Row#n], [Value])).flatten()), caption: [Long table])"
    )
    assert "Row119" in text, text[-500:]
    assert text.count("Repeatmarker") >= 3


def empty_caption(caption):
    Path("main.typ").write_text(prefix + "#fig(rect(), caption: " + caption + ")")
    result = subprocess.run(
        ["typst-guard", "compile"], check=False, capture_output=True, text=True
    )
    assert result.returncode == 1 and "caption" in result.stderr, (
        caption,
        result.stderr,
    )


def overrides():
    for settings, args in (
        ("", 'stroke: rgb("ff0000"), inset: 20pt,'),
        ('#set table(stroke: rgb("ff0000"), inset: 20pt)\n', ""),
    ):
        build(settings + "#plain-table(columns: 2, " + args + " [Insetmarker], [B])")
        assert positions()["Insetmarker"]["xMin"] > 90, positions()
        run("typst", "compile", "--format", "svg", "main.typ", "main.svg")
        assert 'stroke="#ff0000"' in Path("main.svg").read_text(), Path(
            "main.svg"
        ).read_text()
    text = build(
        "#table(columns: 2, table.header(repeat: false, level: 2, [Onceheader], [Value]), ..range(120).map(n => ([Row#n], [Value])).flatten())"
    )
    assert text.count("Onceheader") == 1
    headers = run(
        "typst",
        "eval",
        "--in",
        "main.typ",
        'query(table).map(t => t.children.filter(c => c.func() == table.header).map(h => (repeat: h.at("repeat", default: true), level: h.at("level", default: 1)))).flatten()',
    )
    headers = json.loads(headers)
    assert headers and all(
        header == {"repeat": False, "level": 2} for header in headers
    ), headers


def rules():
    build(
        "#table(columns: 2, table.hline(), table.header(table.hline(), [A], [B], table.hline()), table.vline(), [C], [D])"
    )
    run("typst", "compile", "--format", "svg", "main.typ", "main.svg")
    root = ET.parse("main.svg").getroot()
    paths = [
        p.attrib["d"]
        for p in root.iter()
        if p.tag.endswith("path") and p.attrib.get("stroke") not in (None, "none")
    ]
    assert len(paths) == 3 and all("h " in path for path in paths), paths


def labelled_plain_table():
    for label in ("", " <mine>"):
        build(
            '#set page(numbering: "1")\n#plain-table(columns: 2, stroke: red, inset: 20pt, '
            "table.header([Head], [Value]), [Insetmarker], [B])"
            + label
            + (
                "\n#context assert.eq(query(<mine>).len(), 1)\n"
                '#ref(<mine>, form: "page")'
                if label
                else ""
            )
        )
        assert positions()["Insetmarker"]["xMin"] > 90
        run("typst", "compile", "--format", "svg", "main.typ", "main.svg")
        assert 'stroke="#ff4136"' in Path("main.svg").read_text()


def plain_table_contract():
    build("#plain-table(columns: 2, table.header([Nativehead], [Value]), [A], [B])")
    run("typst", "compile", "--format", "svg", "main.typ", "main.svg")
    assert "v " in Path("main.svg").read_text()
    assert "LibertinusSerif-Bold" not in run("pdffonts", "main.pdf")
    build(
        "#plain-table(columns: 3, table.header(repeat: false, level: 2, table.cell(x: 2)[Last], table.cell(x: 0)[First], table.cell(x: 1)[Middle]), [A], [B], [C])"
    )
    words = positions()
    assert words["First"]["xMin"] < words["Middle"]["xMin"] < words["Last"]["xMin"]
    assert abs(words["First"]["xMin"] - words["A"]["xMin"]) < 0.1
    headers = json.loads(
        run(
            "typst",
            "eval",
            "--in",
            "main.typ",
            "query(table).first().children.filter(c => c.func() == table.header).map(h => (repeat: h.repeat, level: h.level))",
        )
    )
    assert headers == [{"repeat": False, "level": 2}], headers

    build(
        "#plain-table(columns: 3, table.header(table.cell(colspan: 2)[Wide], [Tail]), [A], [B], [C])"
    )
    words = positions()
    assert abs(words["Tail"]["xMin"] - words["C"]["xMin"]) < 0.1


def labelled_ordinary_table():
    build(
        '#set page(numbering: "1")\n#table(columns: 2, table.header([Head], [Value]), [A], [B]) <ordinary>\n#context assert.eq(query(<ordinary>).len(), 1)\n#ref(<ordinary>, form: "page")'
    )
    run("typst", "compile", "--format", "svg", "main.typ", "main.svg")
    svg = Path("main.svg").read_text()
    assert svg.count('stroke-width="0.8"') == 2 and svg.count('stroke-width="0.4"') == 1


def nested_plain_table():
    build(
        "#table(columns: 1, table.header([Outerheader]), [Before #plain-table(columns: 2, [Inner], [Value]) After])"
    )
    run("typst", "compile", "--format", "svg", "main.typ", "main.svg")
    svg = Path("main.svg").read_text()
    assert svg.count('stroke-width="0.8"') == 2 and svg.count('stroke-width="0.4"') == 1


def dependency_outputs():
    from itertools import product

    Path("main.typ").write_text(prefix + "#note[Dependencies]")
    for fmt, joined_deps, joined_format, stdout in product(
        ("json", "make", "zero"), (False, True), (False, True), (False, True)
    ):
        output = "-" if stdout else "native.deps"
        flags = [f"--deps={output}"] if joined_deps else ["--deps", output]
        flags += [f"--deps-format={fmt}"] if joined_format else ["--deps-format", fmt]
        result = subprocess.run(
            ["typst", "compile", "--jobs", "2", "main.typ", "main.pdf", *flags],
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, (flags, result.stderr)
        data = result.stdout if stdout else Path(output).read_bytes()
        assert b"/devkit-typst-packages-" not in data, (flags, data)
        if fmt == "json":
            assert all(Path(name).is_file() for name in json.loads(data)["inputs"])
        elif fmt == "zero":
            assert all(
                Path(os.fsdecode(name)).is_file() for name in data.split(b"\0") if name
            )


def valid_caption(caption):
    Path("logo.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
        '<rect width="10" height="10"/></svg>'
    )
    Path("refs.bib").write_text(
        "@book{k, title={Book}, author={Example, A}, year={2026}}"
    )
    build(
        "= Section <sec>\n#fig(rect(), caption: "
        + caption
        + ")"
        + '\n#bibliography("refs.bib")'
    )


def ordinary_overrides():
    for settings, args in (
        ("", "stroke: red, inset: 20pt,"),
        ("#set table(stroke: red, inset: 20pt)\n", ""),
        ("#show table: set table(stroke: red, inset: 20pt)\n", ""),
    ):
        build(settings + "#table(columns: 2, " + args + "[Insetmarker], [B])")
        assert positions()["Insetmarker"]["xMin"] > 90
        run("typst", "compile", "--format", "svg", "main.typ", "main.svg")
        assert 'stroke="#ff4136"' in Path("main.svg").read_text()
    for settings, call in (
        ("", "table(inset: 20pt,"),
        ("#set table(inset: 20pt)\n", "table("),
        ("#show table: set table(inset: 20pt)\n", "table("),
        ("", "booktabs-table(inset: 20pt,"),
    ):
        build(
            settings
            + "#"
            + call
            + "columns: 2, table.header([A], [B]), [Insetmarker], [D])"
        )
        assert positions()["Insetmarker"]["xMin"] > 90
        assert "LibertinusSerif-Bold" in run("pdffonts", "main.pdf")
        run("typst", "compile", "--format", "svg", "main.typ", "main.svg")
        assert Path("main.svg").read_text().count('stroke-width="0.8"') == 2
    build(
        '#set page(numbering: "1")\n#booktabs-table(inset: 5pt, columns: 2, table.header([A], [B]), [Insetmarker], [D]) <mine>\n#ref(<mine>, form: "page")'
    )
    assert 75 < positions()["Insetmarker"]["xMin"] < 76.5


def header_positions():
    style = (
        Path(os.environ["TYPST_PACKAGE_PATH"])
        / "local/devkit-docs"
        / version
        / "style.typ"
    )
    raw = json.loads(
        run(
            "typst",
            "eval",
            "--root",
            "/",
            f'{{ import "{style}": header-cell; header-cell([Rawheader]) }}',
        )
    )
    assert raw["func"] == "strong", raw
    build(
        "#table(columns: 3, table.header(table.cell(x: 2)[Last], "
        "table.cell(x: 0)[First], table.cell(x: 1)[Middle]), [A], [B], [C])"
    )
    words = positions()
    assert words["First"]["xMin"] < words["Middle"]["xMin"] < words["Last"]["xMin"]
    assert abs(words["First"]["xMin"] - words["A"]["xMin"]) < 0.1
    assert "LibertinusSerif-Bold" in run("pdffonts", "main.pdf")
    build("#table(columns: 2, table.header([Plainheader], [Value]), [A], [B])")
    assert "LibertinusSerif-Bold" in run("pdffonts", "main.pdf")
    assert 76 < positions()["A"]["xMin"] < 78
    run("typst", "compile", "--format", "svg", "main.typ", "main.svg")
    svg = Path("main.svg").read_text()
    assert svg.count('stroke-width="0.8"') == 2
    assert svg.count('stroke-width="0.4"') == 1


def version_policy():
    from vig_utils.typst_packages import verify_registry

    verify_registry(registry)
    for package in (registry / "local/devkit-docs").iterdir():
        Path("old.typ").write_text(
            f'#import "@local/devkit-docs:{package.name}": *\n#show: devkit-document.with()\nRetained import'
        )
        run("typst", "compile", "old.typ", "old.pdf")
    Path("old.typ").unlink()
    assert f"@local/devkit-docs:{version}" in Path(sys.argv[2]).read_text()


def font_environment():
    assert os.environ.get("TYPST_IGNORE_SYSTEM_FONTS") == "true"
    assert "Liberation Sans" not in run("typst", "fonts")
    env = dict(os.environ)
    env.pop("TYPST_IGNORE_SYSTEM_FONTS", None)
    visible = subprocess.run(
        ["typst", "fonts"], env=env, check=True, capture_output=True, text=True
    ).stdout
    assert "Liberation Sans" in visible
    Path("font.typ").write_text('#set text(font: "Liberation Sans")\nFont probe')
    for tool in ("typst", "tinymist"):
        result = subprocess.run(
            [tool, "compile", "font.typ", "font.pdf"],
            check=False,
            capture_output=True,
            text=True,
        )
        assert "unknown font family" in result.stderr, (tool, result.stderr)
    Path("font.typ").unlink()


def public_api_and_layout():
    global prefix
    prefix = prefix.split("#show:")[0] + "#show: devkit-document.with()\n"
    build(
        '#assert.eq(image, std.image)\n#assert.eq(link, std.link)\n#set document(keywords: ("Builtin keyword",))\n#scale(50%)[Builtin scaling]\n#context assert.eq(type-scale.figure-min, 7pt)'
    )
    Path("main.typ").write_text(
        prefix.split("#show:")[0] + '#devkit-document(title: "Wrong")[Body]'
    )
    result = subprocess.run(
        ["typst-guard", "compile"], check=False, capture_output=True, text=True
    )
    assert (
        result.returncode == 1 and "expected function, found module" in result.stderr
    ), result.stderr
    Path("main.typ").write_text(prefix.split("#show:")[0] + "#devkit-document()")
    result = subprocess.run(
        ["typst-guard", "compile"], check=False, capture_output=True, text=True
    )
    assert (
        result.returncode == 1 and "expected function, found module" in result.stderr
    ), result.stderr
    Path("main.typ").write_text(
        prefix.split("#show:")[0] + "#devkit-document.with()[Body]"
    )
    result = subprocess.run(
        ["typst-guard", "compile"], check=False, capture_output=True, text=True
    )
    assert result.returncode == 1 and "#show:" in result.stderr, result.stderr
    build("")
    Path("main.typ").write_text(
        prefix.split("#show:")[0]
        + '#show: devkit-document.with(title: "Long title", short-title: "Running title", authors: "Solo Author")\nBody\n#pagebreak()\nNext page'
    )
    run("typst-guard", "compile")
    run("typst", "compile", "main.typ", "main.pdf")
    pages = run("pdftotext", "-layout", "main.pdf", "-").split("\f")
    assert pages[0].count("Long title") == 1 and pages[0].count("Running title") == 1
    assert pages[1].count("Running title") == 2
    words = positions()
    assert "Solo" in words


def style_contract():
    Path("main.typ").write_text(
        prefix.split("#show:")[0]
        + """#show: devkit-document.with(title: "Metadata title", authors: ("Metadata Author",))
#context { assert.eq(text.lang, "en"); assert.eq(type-scale.figure-min, 7pt) }
= #context assert.eq(text.size, 20pt) Headingone
== #context assert.eq(text.size, 16pt) Headingtwo
=== #context assert.eq(text.size, 13pt) Headingthree
==== #context assert.eq(text.size, 11pt) Headingfour
`Rawmarker`
#fig([Figurebody], caption: [Captionmarker #context assert.eq(text.size, 9pt) #layout(size => assert.eq(size.width, 85% * (210mm - 5cm)))])
#pagebreak()
Second page
"""
    )
    run("typst-guard", "compile")
    run("typst", "compile", "main.typ", "main.pdf")
    text = run("pdftotext", "-layout", "main.pdf", "-")
    assert re.search(r"1\s+Headingone", text) and re.search(
        r"1\.1\s+Headingtwo", text
    ), text
    assert "DejaVuSansMono" in run("pdffonts", "main.pdf")
    info = run("pdfinfo", "main.pdf")
    assert "Metadata title" in info and "Metadata Author" in info
    assert text.split("\f")[1].count("Metadata title") == 2


def kill_style_mutants():
    with tempfile.TemporaryDirectory() as directory:
        copy = Path(directory) / "registry"
        shutil.copytree(registry, copy)
        style = copy / "local/devkit-docs" / version / "style.typ"
        original = style.read_text()
        library = style.with_name("lib.typ")
        library_original = library.read_text()
        style.chmod(0o600)
        library.chmod(0o600)
        mutants = (
            (
                "heading sizes",
                "heading: (20pt, 16pt, 13pt, 11pt)",
                "heading: (21pt, 16pt, 13pt, 11pt)",
            ),
            ("figure minimum", "figure-min: 7pt", "figure-min: 6pt"),
            ("caption size", "caption: 9pt", "caption: 8pt"),
            ("caption width", "width: 85%", "width: 80%"),
            ("raw font", 'font: "DejaVu Sans Mono"', 'font: "Libertinus Serif"'),
            (
                "numbering",
                'set heading(numbering: "1.1")',
                "set heading(numbering: none)",
            ),
            (
                "PDF metadata",
                "set typst-document(title: title, author: authors)",
                "set typst-document(title: none, author: ())",
            ),
            ("language", 'lang: "en"', 'lang: "de"'),
            ("header title", "text(size: type-scale.small, fill: accent, title)", "[]"),
        )
        mutants += (
            (
                "m02 header cell positions",
                "table.cell(..fields, strong(body))",
                "table.cell(strong(body))",
            ),
            ("m03 caption trim", ".trim()", ""),
            (
                "m04 caption body walk",
                'if value.has("body") { return plain-text(value.body) }',
                "",
            ),
            (
                "m05 default inset",
                "fields.inset = (x: 6pt, y: 5pt)",
                "fields.inset = 5pt",
            ),
            (
                "m09 builtin image/link",
                '#import "devkit-document.typ" as devkit-document',
                '#import "devkit-document.typ" as devkit-document\n#let image(..args) = []\n#let link(..args) = []',
            ),
            (
                "m11 header thickness",
                "table.hline(stroke: 0.4pt)",
                "table.hline(stroke: 0.8pt)",
            ),
            ("m14 plain header bold", "return strong(cell)", "return cell"),
        )
        mutants += (
            (
                "S1 plain default stroke",
                'metadata("devkit-plain-table")',
                'metadata("disabled")',
            ),
            (
                "S2 ordinary label",
                'let _ = fields.remove("label", default: none)',
                "let _ = none",
            ),
            (
                "S4 plain header settings",
                "(cell.func())(..fields, ..children.map(mark-plain))",
                "(cell.func())(..children.map(mark-plain))",
            ),
            (
                "S8 plain header cells",
                'table.cell(..fields, metadata("devkit-plain-table") + body)',
                'table.cell(metadata("devkit-plain-table") + body)',
            ),
            ("S9 nested plain table", "if value.func() == table { return false }", ""),
        )
        try:
            os.environ["TYPST_PACKAGE_PATH"] = str(copy)
            for name, before, after in mutants:
                style.write_text(original)
                library.write_text(library_original)
                target, source = (
                    (library, library_original)
                    if name.startswith("m09")
                    else (style, original)
                )
                assert before in source, name
                target.write_text(source.replace(before, after))
                try:
                    if name.startswith(("S1", "S4", "S8")):
                        plain_table_contract()
                    elif name.startswith("S2"):
                        labelled_ordinary_table()
                    elif name.startswith("S9"):
                        nested_plain_table()
                    elif name.startswith(("m02", "m05", "m11", "m14")):
                        header_positions()
                    elif name.startswith("m03"):
                        empty_caption('"  "')
                    elif name.startswith("m04"):
                        empty_caption("[#strong[ ]]")
                    elif name.startswith("m09"):
                        public_api_and_layout()
                    else:
                        style_contract()
                except Exception:
                    print(f"KILLED: {name}", flush=True)
                else:
                    raise AssertionError(f"Surviving mutant: {name}")
        finally:
            os.environ["TYPST_PACKAGE_PATH"] = str(registry)


def package_paths():
    for location in ("outer", "data"):
        root = Path("consumer-" + location).resolve()
        package = root / "local/mypkg/0.1.0"
        package.mkdir(parents=True)
        (package / "typst.toml").write_text(
            '[package]\nname="mypkg"\nversion="0.1.0"\nentrypoint="lib.typ"'
        )
        (package / "lib.typ").write_text("#let marker = [Consumer registry]")
        Path("main.typ").write_text(
            prefix.split("#show:")[0]
            + '#import "@local/mypkg:0.1.0": marker\n#note[Core registry]\n#marker'
        )
        if location == "outer":
            override = root / "local/devkit-docs" / version
            shutil.copytree(registry / "local/devkit-docs" / version, override)
            library = override / "lib.typ"
            library.chmod(0o600)
            library.write_text(
                library.read_text() + '\n#let consumer-origin = "consumer"'
            )
            main = Path("main.typ")
            main.write_text(
                main.read_text() + '\n#assert.eq(consumer-origin, "consumer")'
            )
        env = dict(os.environ)
        env.pop("TYPST_PACKAGE_PATH", None)
        if location == "outer":
            env["TYPST_PACKAGE_PATH"] = str(root)
        else:
            data = Path("data").resolve()
            (data / "typst").mkdir(parents=True)
            (data / "typst/packages").symlink_to(root, target_is_directory=True)
            env["XDG_DATA_HOME"] = str(data)
        Path("justfile").write_text("mod devkit-docs 'docs.justfile'\n")
        Path("docs.justfile").write_text(Path(sys.argv[4]).read_text())
        for command in (
            ["typst", "compile", "main.typ", "main.pdf"],
            ["tinymist", "compile", "main.typ", "main.pdf"],
            [sys.argv[3]],
            ["just", "devkit-docs::typst-canonical", "--deps"],
        ):
            result = subprocess.run(
                command, env=env, check=False, capture_output=True, text=True
            )
            assert result.returncode == 0 and "warning:" not in result.stderr, (
                location,
                command,
                result.stderr,
            )
        deps = json.loads(Path("generated/main.deps.json").read_text())
        assert any("mypkg" in name for name in deps["inputs"]), deps
        assert all(Path(name).is_file() for name in deps["inputs"]), deps


with tempfile.TemporaryDirectory() as directory:
    os.chdir(directory)
    os.environ.update(TYPST_PACKAGE_PATH=str(registry), SOURCE_DATE_EPOCH="0", TZ="UTC")
    for name, test in (
        (
            "first-row colspan",
            lambda: spans("colspan: 3", (("a", "b", "c"), ("d", "e", "f"))),
        ),
        (
            "first-row rowspan",
            lambda: spans("rowspan: 2", (("a", "b"), ("c", "d"), ("e", "f", "g"))),
        ),
        ("long table figure", long_figure),
        *(
            ("empty caption " + caption, lambda c=caption: empty_caption(c))
            for caption in ("[ ]", '"  "', '""', '[#""]', "figure.caption[]")
        ),
        ("table overrides", overrides),
        ("labelled plain table", labelled_plain_table),
        ("plain table defaults and header positions", plain_table_contract),
        ("labelled ordinary table", labelled_ordinary_table),
        ("nested plain table", nested_plain_table),
        ("native dependency spellings and formats", dependency_outputs),
        ("ordinary table overrides", ordinary_overrides),
        ("header positions and rules", header_positions),
        *(
            ("valid caption " + caption, lambda c=caption: valid_caption(c))
            for caption in (
                "[@sec]",
                "[#text(size: 8pt)[Key]]",
                "[#text(red)[Red]]",
                "[#set text(red); Red]",
                "[#cite(<k>)]",
                "[#context [Ctx]]",
                "[#smartquote()]",
                '[#show "a": "b"; abc]',
                '[#image("logo.svg")]',
                "[$x$]",
            )
        ),
        *(
            ("invisible caption " + caption, lambda c=caption: empty_caption(c))
            for caption in (
                "[#sym.zws]",
                '[#"\\u{200B}"]',
                "[#hide[x]]",
                "[#strong[ ]]",
            )
        ),
        ("header rules", rules),
        ("independent package version", version_policy),
        ("font environment", font_environment),
        ("public API and running titles", public_api_and_layout),
        ("style and metadata contracts", style_contract),
        ("consumer package registry", package_paths),
        ("twenty-one style mutants", kill_style_mutants),
    ):
        try:
            test()
            print(f"PASS: {name}", flush=True)
        except Exception as error:
            failures.append(name)
            print(f"FAIL: {name}: {error}", flush=True)
assert not failures, failures
