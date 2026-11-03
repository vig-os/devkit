"""Real compiler acceptance tests for the opt-in content guards (#1994)."""

import hashlib
import json
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest
from vig_utils import typst_guard

ROOT = Path(__file__).resolve().parents[3]
ACTIVE = ROOT / "assets/typst/devkit-docs"
VERSION = tomllib.loads((ACTIVE / "typst.toml").read_text())["package"]["version"]


@pytest.fixture
def doc(tmp_path, monkeypatch):
    registry = tmp_path / ".registry"
    package = registry / "local/devkit-docs" / VERSION
    package.parent.mkdir(parents=True)
    shutil.copytree(ACTIVE, package)
    shutil.copytree(ROOT / "assets/typst/vendor/preview", registry / "preview")
    monkeypatch.setenv("TYPST_PACKAGE_PATH", str(registry))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "0")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "chart.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50" '
        'viewBox="0 0 100 50"><text x="1" y="20" font-size="10">Chart</text></svg>'
    )
    return tmp_path


def write(source, package=False):
    prefix = "// devkit: entry\n"
    if package:
        prefix += f'#import "@local/devkit-docs:{VERSION}": *\n#show: devkit-document.with()\n'
    Path("main.typ").write_text(prefix + source + "\n")


def run(mode="content"):
    return typst_guard.main([mode])


@pytest.mark.parametrize(
    "caption",
    [
        "",
        ", caption: []",
        ', caption: "  "',
        ", caption: [#hide[x]]",
        ", caption: [#strong[ ]]",
        ", caption: [#sym.zws]",
    ],
)
def test_blank_captions(doc, capsys, caption):
    write("#figure(rect()" + caption + ")")
    assert run("figure-caption") == 1
    assert "main.typ:2" in capsys.readouterr().err


@pytest.mark.parametrize(
    "caption",
    ["[Caption]", "[#text(red)[Styled]]", "[$x$]", '[#image("chart.svg")]', "[@sec]"],
)
def test_visible_captions(doc, caption):
    write("= Section <sec>\n#figure(rect(), caption: " + caption + ")")
    assert run("figure-caption") == 0


@pytest.mark.parametrize(
    "mode,source",
    [
        ("figure-caption", "#figure(rect())"),
        ("table-header", "#table([Cell])"),
        ("house-style-bypass", '#set text(font: "Libertinus Serif")'),
        ("house-style-bypass", "#set page(margin: 1cm)"),
        ("figure-text-size", '#image("chart.svg", width: 50pt)'),
    ],
)
def test_bad_suppression_and_skip(doc, capsys, mode, source):
    write(source)
    assert run(mode) == 1
    assert "main.typ:2" in capsys.readouterr().err
    write(source + f" // {mode}: ignore")
    assert run(mode) == 0
    write(source)
    Path(".vig-os").write_text('DEVKIT_TYPST_SKIP="main.typ"\n')
    assert run(mode) == 0


def test_suppression_tracks_includes_functions_and_labels(doc, capsys):
    Path("parts").mkdir()
    Path("parts/body.typ").write_text(
        "#let f() = figure(rect()) // figure-caption: ignore\n#f()\n"
        "#figure(rect()) <unsuppressed>\n"
    )
    write('#include "parts/body.typ"')
    assert run("figure-caption") == 1
    error = capsys.readouterr().err
    assert "parts/body.typ:3" in error
    assert "parts/body.typ:1:" not in error
    Path(".vig-os").write_text('DEVKIT_TYPST_SKIP="parts/**"\n')
    assert run("figure-caption") == 0


def test_headers_and_included_bypasses(doc, capsys):
    write("#table(columns: 2, table.header([A], [B]), [C], [D])")
    assert run("table-header") == 0
    Path("body.typ").write_text(
        '#set /* nested /* comment */ */ text(\n font: "Libertinus Serif",\n)\n'
    )
    write('#include "body.typ"')
    assert run("house-style-bypass") == 1
    assert "body.typ:1" in capsys.readouterr().err
    Path("unused.typ").write_text("#set page(margin: 0pt)")
    Path("body.typ").write_text(
        '// #set page(margin: 0pt)\n/* #set text(font: "Bad") */\n#let x = "#set page()"\n`#set page()`\n#set text(size: 11pt)\n'
    )
    assert run("house-style-bypass") == 0


@pytest.mark.parametrize(
    "source,width",
    [
        ('#image("chart.svg", width: 100pt)', 100),
        ('#image("chart.svg", width: 50%)', (210 / 25.4 * 72 - 2 * 25 / 25.4 * 72) / 2),
        ('#image("chart.svg")', 75),
        ('#grid(columns: (80pt, 1fr), image("chart.svg", width: 100%), [Cell])', 80),
        (
            '#columns(2, gutter: 10pt)[#image("chart.svg", width: 100%)]',
            (210 / 25.4 * 72 - 2 * 25 / 25.4 * 72 - 10) / 2,
        ),
        ('#figure(image("chart.svg", width: 60pt), caption: [Chart])', 60),
    ],
)
def test_package_resolved_widths(doc, source, width):
    write(source, package=True)
    result = subprocess.run(
        [
            "typst",
            "query",
            "--jobs",
            "2",
            "--ignore-system-fonts",
            "--input",
            "devkit-guard-measure=true",
            "main.typ",
            "metadata",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    images = [
        row["value"]
        for row in json.loads(result.stdout)
        if isinstance(row.get("value"), dict)
        and row["value"].get("kind") == "devkit-image"
    ]
    assert len(images) == 1
    assert float(images[0]["width"].removesuffix("pt")) == pytest.approx(
        width, abs=0.02
    )
    assert run("figure-text-size") == int(width * 10 / 100 < 7)


def test_normal_output_unchanged_and_old_package_retained(doc):
    old = "0.1.1"
    old_source = ROOT / "assets/typst/releases/devkit-docs" / old
    assert old_source.is_dir(), "Archive the shipped package before changing it"
    shutil.copytree(old_source, doc / ".registry/local/devkit-docs" / old)
    source = '#figure(image("chart.svg", width: 80pt), caption: [Example])'
    digests = []
    for version in (old, VERSION):
        write(source, package=True)
        p = Path("main.typ")
        p.write_text(
            p.read_text().replace(f"devkit-docs:{VERSION}", f"devkit-docs:{version}")
        )
        subprocess.run(
            [
                "typst",
                "compile",
                "--jobs",
                "2",
                "--ignore-system-fonts",
                "main.typ",
                "out.pdf",
            ],
            check=True,
        )
        digests.append(hashlib.sha256(Path("out.pdf").read_bytes()).hexdigest())
        result = subprocess.run(
            ["typst", "query", "--jobs", "2", "main.typ", "metadata"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "devkit-image" not in result.stdout
    assert digests[0] == digests[1]


@pytest.mark.parametrize(
    "width,expected", [("100pt", 0), ("50pt", 1), ("100%", 0), ("auto", 0)]
)
def test_fallback_widths(doc, width, expected):
    write(f'#image("chart.svg", width: {width})')
    assert run("figure-text-size") == expected


def test_fallback_page_settings_and_unresolved_warning(doc, capsys):
    write('#set page(width: 100pt, margin: 20pt)\n#image("chart.svg", width: 100%)')
    assert run("figure-text-size") == 1
    write('#image("chart.svg", width: 5em)')
    assert run("figure-text-size") == 0
    assert "warning:" in capsys.readouterr().err


def test_svg_inherited_css_transforms_and_units(doc, capsys):
    Path("chart.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50" width="100"><style>.small { font-size: 5px; }</style><g font-size="20"><text x="0" y="20" class="small">Tiny</text></g></svg>'
    )
    write('#image("chart.svg", width: 100pt)')
    assert run("figure-text-size") == 1
    assert "5 pt" in capsys.readouterr().err


def test_malformed_svg_and_raster(doc, capsys):
    write('#image("chart.svg", width: 100pt)')
    Path("chart.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50"><text x="0" y="20" font-size="5">Tiny</text></svg>'
    )
    assert run("figure-text-size") == 1
    assert "7 pt" in capsys.readouterr().err
