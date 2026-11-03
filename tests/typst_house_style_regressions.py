"""Round-two layout regressions, executed with real tools in the Nix sandbox."""

import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

registry = Path(sys.argv[1])
version = next((registry / "local/devkit-docs").iterdir()).name
prefix = f'// devkit: entry\n#import "@local/devkit-docs:{version}": *\n#show: document.with()\n'
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
    assert '"repeat":false' in headers.replace(" ", "").replace("\n", "")
    assert '"level":2' in headers.replace(" ", "").replace("\n", "")


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
    ):
        try:
            test()
            print(f"PASS: {name}", flush=True)
        except AssertionError as error:
            failures.append(name)
            print(f"FAIL: {name}: {error}", flush=True)
assert not failures, failures
