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
version = next((registry / "local/devkit-docs").iterdir()).name
prefix = f'// devkit: entry\n#import "@local/devkit-docs:{version}": *\n#show: devkit-document()\n'
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


def version_policy():
    assert version == "0.1.0", version
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
    prefix = prefix.split("#show:")[0] + "#show: devkit-document()\n"
    build(
        '#set document(keywords: ("Builtin keyword",))\n#scale(50%)[Builtin scaling]\n#context assert.eq(type-scale.figure-min, 7pt)'
    )
    Path("main.typ").write_text(
        prefix.split("#show:")[0] + '#devkit-document(title: "Wrong")[Body]'
    )
    result = subprocess.run(
        ["typst-guard", "compile"], check=False, capture_output=True, text=True
    )
    assert result.returncode == 1 and "#show:" in result.stderr, result.stderr
    Path("main.typ").write_text(prefix.split("#show:")[0] + "#devkit-document()")
    result = subprocess.run(
        ["typst-guard", "compile"], check=False, capture_output=True, text=True
    )
    assert result.returncode == 1 and "function" in result.stderr, result.stderr
    build("")
    Path("main.typ").write_text(
        prefix.split("#show:")[0]
        + '#show: devkit-document(title: "Long title", short-title: "Running title", authors: "Solo Author")\nBody\n#pagebreak()\nNext page'
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
        + """#show: devkit-document(title: "Metadata title", authors: ("Metadata Author",))
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
        style.chmod(0o600)
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
        try:
            os.environ["TYPST_PACKAGE_PATH"] = str(copy)
            for name, before, after in mutants:
                assert before in original, name
                style.write_text(original.replace(before, after))
                try:
                    style_contract()
                except AssertionError:
                    print(f"KILLED: {name}", flush=True)
                else:
                    raise AssertionError(f"Surviving mutant: {name}")
        finally:
            os.environ["TYPST_PACKAGE_PATH"] = str(registry)


def package_paths():
    root = Path("consumer/local/example/0.1.0")
    root.mkdir(parents=True)
    (root / "typst.toml").write_text(
        '[package]\nname="example"\nversion="0.1.0"\nentrypoint="lib.typ"'
    )
    (root / "lib.typ").write_text("#let marker = [Consumer registry]")
    Path("main.typ").write_text(
        prefix.split("#show:")[0]
        + '#import "@local/example:0.1.0": marker\n#note[Core registry]\n#marker'
    )
    env = dict(os.environ, TYPST_PACKAGE_PATH=str(Path("consumer").resolve()))
    result = subprocess.run(
        [sys.argv[3]], env=env, check=False, capture_output=True, text=True
    )
    assert result.returncode == 0 and "warning:" not in result.stderr, result.stderr


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
            for caption in ("[ ]", '""', '[#""]', "figure.caption[]")
        ),
        ("table overrides", overrides),
        ("header rules", rules),
        ("independent package version", version_policy),
        ("font environment", font_environment),
        ("public API and running titles", public_api_and_layout),
        ("style and metadata contracts", style_contract),
        ("consumer package registry", package_paths),
        ("nine style mutants", kill_style_mutants),
    ):
        try:
            test()
            print(f"PASS: {name}", flush=True)
        except AssertionError as error:
            failures.append(name)
            print(f"FAIL: {name}: {error}", flush=True)
assert not failures, failures
