"""Real compiler acceptance tests for the opt-in content guards (#1994)."""

import hashlib
import json
import os
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest
from vig_utils import typst_guard

ASSETS = (
    Path(os.environ["DEVKIT_TYPST_TEST_ASSETS"])
    if "DEVKIT_TYPST_TEST_ASSETS" in os.environ
    else Path(__file__).resolve().parents[3] / "assets/typst"
)
ACTIVE = ASSETS / "devkit-docs"
VERSION = tomllib.loads((ACTIVE / "typst.toml").read_text())["package"]["version"]


@pytest.fixture
def doc(tmp_path, monkeypatch):
    registry = tmp_path / ".registry"
    package = registry / "local/devkit-docs" / VERSION
    package.parent.mkdir(parents=True)
    shutil.copytree(ACTIVE, package)
    shutil.copytree(ASSETS / "vendor/preview", registry / "preview")
    monkeypatch.setenv("TYPST_PACKAGE_PATH", str(registry))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "0")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "chart.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50" '
        'viewBox="0 0 100 50"><text x="1" y="20" font-size="10">Chart</text></svg>'
    )
    (tmp_path / "refs.bib").write_text(
        "@book{k, title={Book}, author={Example, A}, year={2026}}"
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
    [
        "[Caption]",
        "[#text(red)[Styled]]",
        "[$x$]",
        '[#image("chart.svg")]',
        "[@sec]",
        "[#cite(<k>)]",
    ],
)
def test_visible_captions(doc, caption):
    write(
        '#set heading(numbering: "1.")\n= Section <sec>\n#figure(rect(), caption: '
        + caption
        + ")"
    )
    if "cite" in caption:
        with Path("main.typ").open("a") as stream:
            stream.write('\n#bibliography("refs.bib")\n')
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
    old = "0.2.0"
    old_source = ASSETS / "releases/devkit-docs" / old
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


def test_svg_transformed_text_and_unsupported_css(doc, capsys):
    Path("chart.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50"><g transform="scale(0.5)"><text x="0" y="20" font-size="10">Small</text></g></svg>'
    )
    write('#image("chart.svg", width: 100pt)')
    assert run("figure-text-size") == 1
    assert "5 pt" in capsys.readouterr().err
    Path("chart.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50"><style>g text {font-size: 10px}</style><g><text x="0" y="20">Text</text></g></svg>'
    )
    assert run("figure-text-size") == 0
    assert "warning:" in capsys.readouterr().err


def test_marker_in_a_string_is_not_suppression(doc):
    write('#figure(rect(), alt: "// figure-caption: ignore")')
    assert run("figure-caption") == 1


def test_raster_is_skipped(doc):
    import base64

    Path("chart.png").write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII="
        )
    )
    write('#image("chart.png", width: 1pt)')
    assert run("figure-text-size") == 0


def test_source_settings_prose_and_unbalanced_markup(doc):
    write(
        "#set figure(gap: 10pt)\n#set table(inset: 5pt)\nA prose example: figure(example).\n#figure([A (literal], caption: [Caption])\n#table(table.header([Name]), [Value])"
    )
    assert run("content") == 0


def test_repeated_image_call_keeps_each_placed_width(doc, capsys):
    write(
        '#let chart(w) = image("chart.svg", width: w)\n#chart(50pt)\n#chart(100pt)',
        package=True,
    )
    assert run("figure-text-size") == 1
    assert "5 pt" in capsys.readouterr().err


def test_guard_outputs_never_overwrite_consumer_assets(doc):
    write("Hello")
    assets = {
        "guard.pdf": b"Consumer PDF",
        "guard.deps.json": b"Consumer dependency data",
    }
    for name, content in assets.items():
        Path(name).write_bytes(content)
    assert run("content") == 0
    assert {name: Path(name).read_bytes() for name in assets} == assets


@pytest.mark.parametrize("location", ["docs/main.typ", "parts/body.typ"])
def test_image_paths_follow_the_calling_source(doc, capsys, location):
    source = Path(location)
    source.parent.mkdir()
    source.with_name("c.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50" viewBox="0 0 100 50"><text x="0" y="20" font-size="4">Tiny</text></svg>'
    )
    Path("c.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50" viewBox="0 0 100 50"><text x="0" y="20" font-size="30">Decoy</text></svg>'
    )
    if location.startswith("docs"):
        source.write_text('// devkit: entry\n#image("c.svg", width: 100pt)')
    else:
        source.write_text('#image("c.svg", width: 100pt)')
        write('#include "parts/body.typ"')
    assert run("figure-text-size") == 1
    assert location in capsys.readouterr().err
    source.write_text(source.read_text().replace('"c.svg"', '"/c.svg"'))
    assert run("figure-text-size") == 0


@pytest.mark.parametrize("helper", ["table", "booktabs-table", "plain-table"])
def test_package_table_suppression_and_single_finding(doc, capsys, helper):
    write(f"#{helper}([Cell])", package=True)
    assert run("table-header") == 1
    error = capsys.readouterr().err
    assert error.count("table requires table.header") == 1
    assert "main.typ:4" in error
    write(f"#{helper}([Cell]) // table-header: ignore", package=True)
    assert run("table-header") == 0


def test_multiline_local_template_is_a_bypass(doc, capsys):
    template = '#let conf(\n title: none,\n doc,\n) = {\n set page(margin: 1cm)\n set text(font: "Libertinus Serif")\n doc\n}\n#show: conf.with()\nText'
    write(template)
    assert run("house-style-bypass") == 1
    error = capsys.readouterr().err
    assert "main.typ:6" in error and "main.typ:7" in error
    write(
        template.replace(
            "set page(margin: 1cm)",
            "set page(margin: 1cm) // house-style-bypass: ignore",
        ).replace(
            'set text(font: "Libertinus Serif")',
            'set text(font: "Libertinus Serif") // house-style-bypass: ignore',
        )
    )
    assert run("house-style-bypass") == 0


@pytest.mark.parametrize("package", [False, True])
@pytest.mark.parametrize(
    "source",
    [
        '#show figure: it => { assert(it.body.func() == image); it }\n#figure(image("chart.svg", width: 100pt), caption: [Chart])',
        '#let im = image("chart.svg", width: 100pt)\n#im.source\n#im',
        "#let f = figure(rect(), caption: [Chart])\n#f <stored.figure>",
    ],
)
def test_instrumentation_preserves_valid_element_values(doc, source, package):
    write(source, package=package)
    assert run("content") == 0


def test_instrumented_compile_failure_uses_plain_fallback(doc, monkeypatch, capsys):
    from vig_utils import typst_content

    write("Hello")
    original = typst_content.instrument
    monkeypatch.setattr(
        typst_content,
        "instrument",
        lambda *args: '#panic("guard-only failure")\n' + original(*args),
    )
    assert run("content") == 0
    assert "warning:" in capsys.readouterr().err
    write("#undefined()")
    assert run("content") == 1


def test_one_mirror_for_all_entries(doc, monkeypatch):
    from vig_utils import typst_content

    write("Hello")
    Path("second.typ").write_text("// devkit: entry\nSecond")
    calls = []
    original = typst_content.prepare_tree

    def prepare(*args):
        calls.append(args[0])
        return original(*args)

    monkeypatch.setattr(typst_content, "prepare_tree", prepare)
    assert run("content") == 0
    assert len(calls) == 1


def test_typst_scale_warns_about_unresolved_physical_size(doc, capsys):
    write('#scale(50%)[#image("chart.svg", width: 100pt)]', package=True)
    assert run("figure-text-size") == 0
    error = capsys.readouterr().err
    assert "warning:" in error and "scale" in error


@pytest.mark.parametrize("fit,expected", [("contain", 1), ("stretch", 1), ("cover", 0)])
@pytest.mark.parametrize("package", [False, True])
def test_image_fit_uses_both_dimensions(doc, fit, expected, package):
    write(
        f'#image("chart.svg", width: 100pt, height: 10pt, fit: "{fit}")',
        package=package,
    )
    assert run("figure-text-size") == expected


def test_height_only_and_viewbox_meet(doc):
    write('#image("chart.svg", height: 10pt)')
    assert run("figure-text-size") == 1
    Path("chart.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="50" viewBox="0 0 100 100"><text x="0" y="20" font-size="20">Tiny after meet</text></svg>'
    )
    write('#image("chart.svg", width: 100pt)')
    assert run("figure-text-size") == 1


def test_boundary_and_measured_grid_width(doc):
    write('#image("chart.svg", width: 70pt)')
    assert run("figure-text-size") == 0  # Exactly seven points is readable.
    write(
        '#grid(columns: (60pt, 1fr), image("chart.svg", width: 100%), [Cell])',
        package=True,
    )
    assert run("figure-text-size") == 1  # The page-width fallback would pass.
    write("#grid(columns: 2, [A], [B])", package=True)
    assert run("table-header") == 0


def test_auto_width_caps_large_intrinsic_images(doc):
    Path("chart.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="2000" height="1000" viewBox="0 0 2000 1000"><text x="0" y="20" font-size="10">Tiny after cap</text></svg>'
    )
    write('#image("chart.svg")')
    assert run("figure-text-size") == 1


def test_matplotlib_doctype_is_measured(doc, capsys):
    fixtures = (
        Path(os.environ["DEVKIT_TYPST_CONTENT_FIXTURES"])
        if "DEVKIT_TYPST_CONTENT_FIXTURES" in os.environ
        else Path(__file__).parent / "fixtures/typst-content"
    )
    shutil.copyfile(fixtures / "matplotlib.svg", "chart.svg")
    write('#image("chart.svg", width: 144pt)')
    assert run("figure-text-size") == 1
    error = capsys.readouterr().err
    assert "DOCTYPE" not in error and "cannot measure" not in error


@pytest.mark.parametrize("first", [True, False])
@pytest.mark.parametrize("nested", [True, False])
def test_scale_warning_does_not_hide_another_placement(doc, capsys, first, nested):
    scaled = '#scale(50%)[#image("chart.svg", width: 100pt)]'
    if nested:
        scaled = "#scale(50%)[" + scaled + "]"
    plain = '#image("chart.svg", width: 50pt)'
    write("\n\n".join((scaled, plain) if first else (plain, scaled)), package=True)
    assert run("figure-text-size") == 1
    error = capsys.readouterr().err
    assert "warning:" in error and "5 pt" in error


@pytest.mark.parametrize("version", ["3.6", "3.8", "3.9", "3.10"])
def test_matplotlib_font_forms(doc, capsys, version):
    # Representative text emitted by Matplotlib with svg.fonttype='none'.
    size = (
        "font-size: 5px; font-family: 'DejaVu Sans'"
        if version == "3.10"
        else "font: 5px 'DejaVu Sans'"
    )
    Path("chart.svg").write_text(
        '<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="72pt" height="36pt" viewBox="0 0 100 50"><text style="{size}" x="10" y="20">0.5</text></svg>'
    )
    write('#image("chart.svg", width: 69.4pt)')
    assert run("figure-text-size") == 1
    assert "3.47 pt" in capsys.readouterr().err


@pytest.mark.parametrize(
    "source",
    [
        "#let conf = (\n doc,\n) => {\n set page(margin: 1cm)\n doc\n}\n#show: conf",
        '#show: (\n doc\n) => {\n set text(font: "Libertinus Serif")\n doc\n}',
        '#import "closure.typ": conf\n#show: conf',
    ],
)
def test_multiline_closure_bypass(doc, source):
    Path("closure.typ").write_text(
        "#let conf = (\n doc,\n) => {\n set page(margin: 1cm)\n doc\n}"
    )
    write(source)
    assert run("house-style-bypass") == 1
    Path("closure.typ").write_text(
        Path("closure.typ")
        .read_text()
        .replace(
            "set page(margin: 1cm)",
            "set page(margin: 1cm) // house-style-bypass: ignore",
        )
    )
    write(
        source.replace(
            "set page(margin: 1cm)",
            "set page(margin: 1cm) // house-style-bypass: ignore",
        ).replace(
            'set text(font: "Libertinus Serif")',
            'set text(font: "Libertinus Serif") // house-style-bypass: ignore',
        )
    )
    assert run("house-style-bypass") == 0


def test_fallback_figure_origins_only_active_files_in_document_order(doc, capsys):
    Path("unused.typ").write_text("#figure(rect()) // figure-caption: ignore")
    Path("z.typ").write_text("#let z = figure(rect())\n#z <stored.z>")
    Path("a.typ").write_text(
        "#let a = figure(rect()) // figure-caption: ignore\n#a <stored.a>"
    )
    write('#include "z.typ"\n#include "a.typ"')
    assert run("figure-caption") == 1
    output = capsys.readouterr().err
    assert "z.typ:1: figure-caption:" in output
    assert "a.typ:1: figure-caption:" not in output


@pytest.mark.parametrize("first", [True, False])
def test_duplicate_labels_have_independent_suppression(doc, capsys, first):
    calls = [
        "#figure(rect()) <same> // figure-caption: ignore",
        "#figure(rect()) <same>",
    ]
    write("\n".join(calls if first else reversed(calls)))
    assert run("figure-caption") == 1
    output = capsys.readouterr().err
    assert f"main.typ:{3 if first else 2}: figure-caption:" in output
    assert output.count("figure requires a non-empty caption") == 1


def test_generated_assets_and_variable_source_paths(doc, capsys):
    Path("generated").mkdir()
    Path("docs").mkdir()
    Path("generated/plot.svg").write_text(Path("chart.svg").read_text())
    Path("docs/chart.svg").write_text(
        Path("chart.svg").read_text().replace('font-size="10"', 'font-size="5"')
    )
    Path("docs/part.typ").write_text('#let p = "chart.svg"\n#image(p, width: 100pt)')
    write('#image("generated/plot.svg", width: 50pt)\n#include "docs/part.typ"')
    assert run("figure-text-size") == 1
    output = capsys.readouterr().err
    assert "generated/plot.svg: smallest text is 5 pt" in output
    assert "docs/chart.svg: smallest text is 5 pt" in output
    assert "cannot measure" not in output


@pytest.mark.parametrize("suppress", [False, True])
def test_logo_origin_and_independent_body_measurement(doc, capsys, suppress):
    Path("chart.svg").write_text(
        Path("chart.svg")
        .read_text()
        .replace('height="50"', 'height="100"')
        .replace("0 0 100 50", "0 0 100 100")
    )
    marker = " // figure-text-size: ignore" if suppress else ""
    Path("main.typ").write_text(
        f'// devkit: entry\n#import "@local/devkit-docs:{VERSION}": *\n'
        f'#show: devkit-document.with(logo: path("chart.svg")){marker}\n'
        '#image("chart.svg", width: 100pt)\n'
    )
    assert run("figure-text-size") == (0 if suppress else 1)
    output = capsys.readouterr().err
    if not suppress:
        assert "main.typ:3: figure-text-size:" in output
        assert output.count("minimum is 7 pt") == 1
    else:
        assert "minimum is 7 pt" not in output


def test_instrumentation_warning_triggers_plain_fallback(doc, monkeypatch, capsys):
    from vig_utils import typst_content

    write("Hello")
    original = typst_content.instrument
    monkeypatch.setattr(
        typst_content,
        "instrument",
        lambda *args: '#text(font: "Nonexistent Guard Font")[X]\n' + original(*args),
    )
    assert run("content") == 0
    assert "using plain fallback" in capsys.readouterr().err


def test_unknown_font_warns_and_default_cover_is_used(doc, capsys):
    Path("chart.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50" viewBox="0 0 100 50"><text style="font: caption">x</text></svg>'
    )
    # Typst itself cannot decode unknown font shorthand; validate guard warnings
    # via the same SVG inspection/reporting path independently of the compiler.
    from collections import defaultdict, deque

    from vig_utils.typst_content import check_svg

    findings = []

    def report(*args, **kwargs):
        findings.append((args, kwargs))
        return 0

    check_svg({"source": "chart.svg", "width": "100pt"}, defaultdict(deque), report)
    assert findings[0][1]["warning"]
    Path("chart.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50" viewBox="0 0 100 50"><text font-size="10">x</text></svg>'
    )
    write('#image("chart.svg", width: 50pt, height: 100pt)')
    assert run("figure-text-size") == 0  # Default cover gives 20pt, contain 5pt.
    assert (
        check_svg(
            {"source": "chart.svg", "_placed": {"width": "50pt", "height": "100pt"}},
            defaultdict(deque),
            lambda *args, **kwargs: 1,
        )
        == 0
    )


def test_only_dependency_sources_are_instrumented(doc, monkeypatch):
    from vig_utils import typst_content

    write("Hello")
    Path("unrelated.typ").write_text("#figure(rect())")
    original = typst_content.instrument
    seen = []

    def instrument(source, name, origins):
        seen.append(name)
        return original(source, name, origins)

    monkeypatch.setattr(typst_content, "instrument", instrument)
    assert run("content") == 0
    assert seen == ["main.typ"]


def test_fallback_label_suppression_does_not_cross_entries(doc, capsys):
    Path("a.typ").write_text(
        "// devkit: entry\n#figure(rect()) <shared> // figure-caption: ignore\n"
    )
    write("#let f = figure(rect())\n#f <shared>")
    assert run("figure-caption") == 1
    output = capsys.readouterr().err
    assert "main.typ:2: figure-caption:" in output
    assert "a.typ:2: figure-caption:" not in output


def test_caption_prose_preserves_grid_measurement(doc, capsys):
    write(
        '#grid(columns: (63pt, 1fr), figure(image("chart.svg", width: 100%), caption: [Runs, see table(s) 2-3]), [Cell])',
        package=True,
    )
    assert run("figure-text-size") == 1
    output = capsys.readouterr().err
    assert "smallest text is 6.3 pt" in output
    assert "using plain fallback" not in output


@pytest.mark.parametrize(
    "prose",
    ["the table(columns: 2) call", "figure(rect())", "never set page(margin: 1cm)"],
)
@pytest.mark.parametrize("nested", [False, True])
def test_inline_markup_does_not_enable_prose_calls(doc, prose, nested):
    write(f"#emph[{prose}]" if nested else f"#emph[Example] {prose}")
    assert run("content") == 0


@pytest.mark.parametrize("package", [False, True])
def test_dictionary_logo_cannot_suppress_body_image(doc, capsys, package):
    write(
        '#let unrelated = (logo: path("chart.svg")) // figure-text-size: ignore\n#image("chart.svg", width: 20pt)',
        package=package,
    )
    assert run("figure-text-size") == 1
    assert "smallest text is 2 pt" in capsys.readouterr().err


@pytest.mark.parametrize(
    "css",
    [
        "FONT: 5px sans-serif",
        "/* label */ font: 5px sans-serif",
        "font: 5px sans-serif ! important",
    ],
)
@pytest.mark.parametrize("inline", [True, False])
def test_unsupported_css_font_syntax_warns(doc, capsys, css, inline):
    body = (
        f'<text style="{css}">x</text>'
        if inline
        else f"<style>text {{{css}}}</style><text>x</text>"
    )
    Path("chart.svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50" viewBox="0 0 100 50">{body}</svg>'
    )
    write('#image("chart.svg", width: 100pt)')
    assert run("figure-text-size") == 0
    output = capsys.readouterr().err
    assert "warning:" in output
    assert "cannot measure chart.svg" in output


@pytest.mark.parametrize(
    "mode,source",
    [
        ("figure-caption", "#figure(\n rect()\n)"),
        ("table-header", "#table(\n [Cell]\n)"),
        ("house-style-bypass", "#set page(\n margin: 1cm\n)"),
        ("figure-text-size", '#image(\n "chart.svg", width: 20pt\n)'),
    ],
)
def test_closing_line_suppression(doc, mode, source):
    write(source)
    assert run(mode) == 1
    write(source + f" // {mode}: ignore")
    assert run(mode) == 0


def test_bypass_findings_are_scoped_to_each_entry(doc, capsys):
    Path("a.typ").write_text("// devkit: entry\n#set page(margin: 1cm)\nExample\n")
    write("Hello")
    assert run("house-style-bypass") == 1
    output = capsys.readouterr().err
    assert output.count("a.typ:2: house-style-bypass:") == 1
    assert "main.typ:" not in output


@pytest.mark.parametrize(
    "setting",
    ["page(margin: 1cm)", 'page(paper: "a5")', 'text(font: "New Computer Modern")'],
)
@pytest.mark.parametrize("heading", [False, True])
def test_runtime_bypass_without_source_setting(doc, capsys, setting, heading):
    # Alias calls deliberately evade the source scan; contextual metadata must
    # observe the effective style at the page start and at headings.
    name, args = setting.split("(", 1)
    source = f"#let apply = {name}\n#show: body => {{ set apply({args}; body }}\n"
    source += "= Changed\nText" if heading else "Text"
    write(source, package=True)
    assert run("house-style-bypass") == 1
    assert "detected at runtime on page 1" in capsys.readouterr().err
    Path("main.typ").write_text(
        "// house-style-bypass: ignore-document\n" + Path("main.typ").read_text()
    )
    assert run("house-style-bypass") == 0


def test_runtime_bypass_observes_later_page_and_heading(doc, capsys):
    write(
        '#let apply = text\nNormal\n#pagebreak()\n#show: body => { set apply(font: "New Computer Modern"); body }\n= Changed\nText',
        package=True,
    )
    assert run("house-style-bypass") == 1
    assert "detected at runtime on page 2" in capsys.readouterr().err


def test_runtime_marker_is_entry_scoped_and_keeps_source_findings(doc, capsys):
    marker = "// house-style-bypass: ignore-document"
    Path("part.typ").write_text(marker + "\nIncluded")
    write(
        '#let apply = text\n#show: body => { set apply(font: "New Computer Modern"); body }\n#include "part.typ"',
        package=True,
    )
    assert run("house-style-bypass") == 1
    assert "detected at runtime" in capsys.readouterr().err
    write(
        f'#let example = "{marker}"\n#set page(margin: 1cm)\nText\n{marker}',
        package=True,
    )
    assert run("house-style-bypass") == 1
    output = capsys.readouterr().err
    assert "main.typ:5: house-style-bypass:" in output
    assert "detected at runtime" not in output


def test_runtime_heading_sees_midpage_font_override(doc, capsys):
    write(
        'Normal\n\n#let apply = text\n#set apply(font: "New Computer Modern")\n= Changed\nText',
        package=True,
    )
    assert run("house-style-bypass") == 1
    assert "detected at runtime on page 1" in capsys.readouterr().err


def test_runtime_page_probe_survives_custom_header(doc, capsys):
    write(
        "#let apply = page\n#set apply(margin: 1cm, header: none)\nText", package=True
    )
    assert run("house-style-bypass") == 1
    assert "detected at runtime on page 1" in capsys.readouterr().err
