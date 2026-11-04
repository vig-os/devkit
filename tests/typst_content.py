"""Real compiler acceptance tests for content helpers (#1994)."""

import json
import os
import re
import subprocess
import tomllib
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ASSETS = Path(
    os.environ.get(
        "DEVKIT_TYPST_ASSETS", Path(__file__).resolve().parents[1] / "assets/typst"
    )
)


@pytest.fixture
def project(tmp_path, monkeypatch):
    registry = tmp_path / "registry"
    local = registry / "local/devkit-docs"
    local.mkdir(parents=True)
    (registry / "preview").symlink_to(
        ASSETS / "vendor/preview", target_is_directory=True
    )
    for package in (ASSETS / "releases/devkit-docs").iterdir():
        (local / package.name).symlink_to(package, target_is_directory=True)
    version = tomllib.loads((ASSETS / "devkit-docs/typst.toml").read_text())["package"][
        "version"
    ]
    (local / version).symlink_to(ASSETS / "devkit-docs", target_is_directory=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TYPST_PACKAGE_PATH", str(registry))
    monkeypatch.setenv("TYPST_PACKAGE_CACHE_PATH", str(tmp_path / "cache"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "0")
    monkeypatch.setenv("TZ", "UTC")
    Path("glossary.yaml").write_text(
        "- id: sample\n  term: Sample\n  definition: A specimen.\n  kind: term\n"
        "- id: cpu\n  term: CPU\n  definition: Central processing unit\n  kind: acronym\n"
        "- id: unused\n  term: Unusedmarker\n  definition: Never referenced.\n  kind: term\n"
    )
    return f'#import "@local/devkit-docs:{version}": *\n'


def compile_source(source, *inputs):
    Path("main.typ").write_text("// devkit: entry\n" + source)
    return subprocess.run(
        [
            "typst",
            "compile",
            "--root",
            ".",
            "--ignore-system-fonts",
            "--jobs",
            "2",
            *inputs,
            "main.typ",
            "main.pdf",
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def pdf_text():
    return subprocess.run(
        ["pdftotext", "-layout", "main.pdf", "-"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def test_plot_offline_and_rendered_sizes(project):
    result = compile_source(
        project
        + """#show: devkit-document.with()
#fig(plot((0, 1, 2), (1, 3, 2), xlabel: [Time (s)], ylabel: [Distance (m)]), caption: [Trajectory])
"""
    )
    assert result.returncode == 0, result.stderr
    assert "warning:" not in result.stderr
    assert "Trajectory" in pdf_text() and "Time" in pdf_text()
    subprocess.run(
        ["pdftohtml", "-xml", "-zoom", "1", "main.pdf", "plot.xml"],
        check=True,
        capture_output=True,
    )
    sizes = [float(n.attrib["size"]) for n in ET.parse("plot.xml").iter("fontspec")]
    assert sizes and min(sizes) >= 7, sizes


@pytest.mark.parametrize(
    "labels",
    [
        "",
        "xlabel: [X]",
        "ylabel: [Y]",
        "xlabel: [], ylabel: [Y]",
        "xlabel: [X], ylabel: [ ]",
    ],
)
def test_plot_requires_both_labels(project, labels):
    result = compile_source(project + f"#plot((0, 1), (0, 1), {labels})")
    assert result.returncode != 0 and "plot requires" in result.stderr, result.stderr


def test_plot_in_fig_requires_caption(project):
    result = compile_source(
        project + "#fig(plot((0, 1), (0, 1), xlabel: [X], ylabel: [Y]))"
    )
    assert result.returncode != 0 and "caption" in result.stderr, result.stderr


def test_glossary_used_terms_and_acronym_first_use(project):
    project += '#show: glossary-setup.with(yaml("/glossary.yaml"))\n'
    Path("shared.typ").write_text(
        project.split("#show:")[0] + '#term("cpu"), #term("cpu"). #term("sample").'
    )
    result = compile_source(
        project
        + """#show: devkit-document.with()
#include "shared.typ"
#term("cpu").
#glossary()
"""
    )
    assert result.returncode == 0, result.stderr
    text = pdf_text()
    assert "Central processing unit (CPU), CPU." in text
    assert "A specimen." in text
    assert "Unusedmarker" not in text
    assert text.count("Central processing unit") == 2


def test_glossary_unknown_id_fails(project):
    project += '#show: glossary-setup.with(yaml("/glossary.yaml"))\n'
    result = compile_source(project + '#term("absent")')
    assert result.returncode != 0 and "unknown glossary id" in result.stderr, (
        result.stderr
    )


def test_glossary_custom_register(project):
    project += '#show: glossary-setup.with(yaml("/glossary.yaml"))\n'
    Path("terms.yaml").write_text(Path("glossary.yaml").read_text())
    Path("glossary.yaml").unlink()
    result = compile_source(
        project.replace("/glossary.yaml", "/terms.yaml") + '#term("sample")'
    )
    assert result.returncode == 0, result.stderr
    assert "Sample" in pdf_text()


def test_slides_layout_branding_stamp_and_tables(project):
    result = compile_source(
        project
        + """#show: slides.with(title: [Deckmarker], subtitle: [Subtitlemarker], authors: ("Example Author",), accent: rgb("174f79"))
#section-slide[Sectionmarker]
#slide(title: [Contentmarker])[
#context { assert.eq(page.width / page.height, 16 / 9); assert.eq(text.size, type-scale.body) }
#table(columns: 2, table.header([Headermarker], [Value]), [Sample], number(2))
#fig(rect(), caption: [Captionmarker])
]
""",
        "--input",
        "rev=abc12345",
    )
    assert result.returncode == 0, result.stderr
    text = pdf_text()
    for marker in (
        "Deckmarker",
        "Subtitlemarker",
        "Sectionmarker",
        "Contentmarker",
        "Headermarker",
        "Captionmarker",
        "Example Author",
    ):
        assert marker in text
    assert text.count("abc12345") == 3
    assert len(text.rstrip("\n\f").split("\f")) == 3
    query = subprocess.run(
        ["typst", "query", "--root", ".", "main.typ", "figure"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(query.stdout)[0]["caption"] is not None


def test_slides_fig_requires_caption(project):
    result = compile_source(project + "#show: slides.with()\n#slide()[#fig(rect())]")
    assert result.returncode != 0 and "caption" in result.stderr, result.stderr


@pytest.mark.parametrize("label", ["text(size: 6pt)[Tiny]", "text(size: 0.5em)[Tiny]"])
def test_plot_rejects_undersized_label_text(project, label):
    result = compile_source(
        project + f"#plot((0, 1), (0, 1), xlabel: {label}, ylabel: [Y])"
    )
    assert result.returncode != 0 and "7 pt" in result.stderr, result.stderr


def test_plot_dimensions_preserve_text_size(project):
    result = compile_source(
        project
        + """#set text(size: 5pt)
#plot((0, 1), (0, 1), width: 3cm, height: 2cm, xlabel: [X], ylabel: [Y])
"""
    )
    assert result.returncode == 0, result.stderr
    subprocess.run(
        ["pdftohtml", "-xml", "-zoom", "1", "main.pdf", "small.xml"],
        check=True,
        capture_output=True,
    )
    sizes = [float(n.attrib["size"]) for n in ET.parse("small.xml").iter("fontspec")]
    assert sizes and min(sizes) >= 7


def test_empty_glossary_and_canonical_slides(project):
    source = (
        project
        + '#show: glossary-setup.with(yaml("/glossary.yaml"))\n'
        + "#show: slides.with(title: [Canonical])\n#slide()[Body #glossary()]"
    )
    result = compile_source(source)
    assert result.returncode == 0, result.stderr
    first = Path("main.pdf").read_bytes()
    assert "Glossary" not in pdf_text()
    assert compile_source(source).returncode == 0
    assert Path("main.pdf").read_bytes() == first


def test_plot_scientific_ticks_and_math_labels_remain_readable(project):
    result = compile_source(
        project
        + """#plot((1000000, 2000000), (0.0000001, 0.0000002), xlabel: [$x_(i_j)$], ylabel: [Y])"""
    )
    assert result.returncode == 0, result.stderr
    subprocess.run(
        ["pdftohtml", "-xml", "-zoom", "1", "main.pdf", "scientific.xml"],
        check=True,
        capture_output=True,
    )
    sizes = [
        float(n.attrib["size"]) for n in ET.parse("scientific.xml").iter("fontspec")
    ]
    assert sizes and min(sizes) >= 7, sizes


def pdf_words():
    result = subprocess.run(
        ["pdftotext", "-bbox", "main.pdf", "-"],
        check=True,
        capture_output=True,
        text=True,
    )
    return list(ET.fromstring(result.stdout).iter("{http://www.w3.org/1999/xhtml}word"))


@pytest.mark.parametrize(
    "label", [r"#super[\*]", "#sub(typographic: false)[2]", "$text(size: #4pt, x)$"]
)
def test_plot_script_and_math_text_floor(project, label):
    result = compile_source(
        project + f"#plot((0, 1), (0, 1), xlabel: [{label}], ylabel: [Y])"
    )
    if result.returncode:
        assert "7 pt" in result.stderr, result.stderr
    else:
        subprocess.run(
            ["pdftohtml", "-xml", "-zoom", "1", "main.pdf", "floor.xml"],
            check=True,
            capture_output=True,
        )
        sizes = [
            float(n.attrib["size"]) for n in ET.parse("floor.xml").iter("fontspec")
        ]
        assert min(sizes) >= 7, sizes


def test_plot_ticks_and_labels_use_small_scale(project):
    result = compile_source(
        project
        + "#show: devkit-document.with()\n#plot((0, 1), (0, 1), xlabel: [Xmarker], ylabel: [Ymarker])"
    )
    assert result.returncode == 0, result.stderr
    subprocess.run(
        ["pdftohtml", "-xml", "-zoom", "1", "main.pdf", "ticks.xml"],
        check=True,
        capture_output=True,
    )
    root = ET.parse("ticks.xml")
    sizes = {n.attrib["id"]: float(n.attrib["size"]) for n in root.iter("fontspec")}
    for node in root.iter("text"):
        if "".join(node.itertext()).strip() in {"0.0", "1.0", "Xmarker", "Ymarker"}:
            assert sizes[node.attrib["font"]] == 9


@pytest.mark.parametrize("wrapper", ["= Using {}", "#fig(rect(), caption: [Using {}])"])
def test_glossary_body_first_use_and_sorted_unique_appendix(project, wrapper):
    project += '#show: glossary-setup.with(yaml("/glossary.yaml"))\n'
    result = compile_source(
        project
        + '\n#outline()\n#outline(target: figure)\n= Using #term("cpu")\n#fig(rect(), caption: [About #term("sample")])\n#term("sample"). #term("cpu").\n#glossary()'.replace(
            '= Using #term("cpu")', wrapper.format('#term("cpu")')
        )
    )
    assert result.returncode == 0, result.stderr
    text = " ".join(pdf_text().split())
    assert text.count("Using Central processing unit (CPU)") == 1, text
    assert text.count("Using CPU") == 1, text
    assert text.index("Using CPU") < text.index(
        "Using Central processing unit (CPU)"
    ), text
    assert "A specimen. (Sample)" not in text
    appendix = text.split("Glossary")[-1]
    assert appendix.index("CPU") < appendix.index("Sample"), appendix
    assert appendix.count("Sample") == 1


def test_large_glossary_plain_compile(project):
    project += '#show: glossary-setup.with(yaml("/glossary.yaml"))\n'
    path = Path("glossary.yaml")
    path.write_text(path.read_text() + "#" + "padding" * 23000 + "\n")
    result = compile_source(project + '#term("sample")')
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("duplicate", [False, True])
def test_glossary_diagnostics(project, duplicate):
    project += '#show: glossary-setup.with(yaml("/glossary.yaml"))\n'
    if duplicate:
        path = Path("glossary.yaml")
        path.write_text(path.read_text() + path.read_text())
        expected = "duplicate glossary id"
    else:
        project = project.split("#show: glossary-setup")[0]
        expected = "no glossary loaded; see"
    result = compile_source(project + '#term("sample")')
    assert result.returncode != 0 and expected in result.stderr, result.stderr


def test_slides_long_short_title_does_not_overlap_counter(project):
    result = compile_source(
        project
        + "#show: slides.with(short-title: [ABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZ])\n#slide()[Body]"
    )
    assert result.returncode == 0, result.stderr
    words = pdf_words()
    title = next(w for w in words if (w.text or "").startswith("ABC"))
    counter = next(w for w in words if w.text == "1")
    assert float(title.attrib["xMax"]) < float(counter.attrib["xMin"])
    assert all(
        float(w.attrib["yMax"]) <= float(counter.attrib["yMax"]) + 1
        for w in words
        if (w.text or "").startswith("ABC")
    )


@pytest.mark.parametrize(
    "title",
    [
        "Results for *Q3* with $alpha$ decay",
        "Water H#sub[2]O and m#super[2] data",
        "Before #box[Boxmarker] after",
        'Before #image("marker.svg", height: 8pt) after',
    ],
)
def test_slide_footer_preserves_content(project, title):
    Path("marker.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="10"><rect width="20" height="10" fill="red"/></svg>'
    )
    result = compile_source(
        project + f"#show: slides.with(short-title: [{title}])\n#slide()[Body]"
    )
    assert result.returncode == 0, result.stderr
    text = unicodedata.normalize("NFKC", " ".join(pdf_text().split()))
    if "Q3" in title:
        assert "Results for Q3 with α decay" in text, text
        fonts = subprocess.run(
            ["pdffonts", "main.pdf"], check=True, capture_output=True, text=True
        )
        assert "Bold" in fonts.stdout
    elif "Water" in title:
        assert "Water H" in text and "O and m" in text and "data" in text, text
        assert "2" in text, text
    else:
        assert "Before" in text and "after" in text and "visible" not in text, text
        if "box" in title:
            assert "Before Boxmarker after" in text, text
        else:
            # SVG is drawn as vectors; its red rectangle must survive export.
            subprocess.run(
                ["pdftocairo", "-svg", "main.pdf", "footer.svg"],
                check=True,
                capture_output=True,
            )
            assert "100%,0%,0%" in Path("footer.svg").read_text().replace(" ", "")


@pytest.mark.parametrize("script", ["super", "sub"])
def test_plot_uses_synthesized_scripts_at_seven_points(project, script):
    result = compile_source(
        project + f"#plot((0, 1), (0, 1), xlabel: [m#{script}[2]], ylabel: [Y])"
    )
    assert result.returncode == 0, result.stderr
    subprocess.run(
        ["pdftohtml", "-xml", "-zoom", "1", "main.pdf", "script.xml"],
        check=True,
        capture_output=True,
    )
    root = ET.parse("script.xml")
    sizes = {n.attrib["id"]: float(n.attrib["size"]) for n in root.iter("fontspec")}
    assert any(
        "".join(n.itertext()).strip() == "2" and sizes[n.attrib["font"]] == 7
        for n in root.iter("text")
    )


@pytest.mark.parametrize(
    "source,expected",
    [
        (
            "#glossary()",
            "no glossary loaded; see https://github.com/vig-os/devkit/blob/dev/docs/NIX.md#house-style-package",
        ),
        ("#show: glossary-setup.with(())\n#glossary()", "empty glossary register"),
    ],
)
def test_glossary_setup_errors_are_actionable(project, source, expected):
    result = compile_source(project + source)
    assert result.returncode != 0 and expected in result.stderr, result.stderr


def test_footnote_first_term_expands_in_footnote(project):
    result = compile_source(
        project
        + '#show: glossary-setup.with(yaml("/glossary.yaml"))\nStart#footnote[Footnote #term("cpu").]\n\nLaterbody #term("cpu").'
    )
    assert result.returncode == 0, result.stderr
    text = " ".join(pdf_text().split())
    assert (
        "Laterbody CPU." in text and "Footnote Central processing unit (CPU)." in text
    ), text


def test_register_bound_term_has_bookmark_text(project):
    result = compile_source(
        project
        + '#let g = glossary-tools(yaml("/glossary.yaml"))\n#let term = g.term\n#show: g.setup\n#outline()\n= Using #term("cpu")\n#term("cpu")\n#glossary()',
        "--pretty",
    )
    assert result.returncode == 0, result.stderr
    assert b"/Title (Using CPU)" in Path("main.pdf").read_bytes()
    text = " ".join(pdf_text().split())
    assert text.index("Using CPU") < text.index("Using Central processing unit (CPU)")


@pytest.mark.parametrize(
    "wrapper,font",
    [
        ("strong", "Bold"),
        ("emph", "Italic"),
        ('text.with(fill: rgb("ff0000"))', None),
        ("smallcaps", None),
        ('link.with("https://example.com")', None),
    ],
)
@pytest.mark.parametrize("single_word", [False, True])
def test_long_styled_footer_keeps_prefix(project, wrapper, font, single_word):
    value = "Prefixmarker" + (
        "abcdefghij" * 80 if single_word else " extended research area facility" * 20
    )
    result = compile_source(
        project
        + f"#show: slides.with(short-title: {{ let style = {wrapper}; style([{value}]) }})\n#slide()[Body]"
    )
    assert result.returncode == 0, result.stderr
    words = pdf_words()
    footer = [w for w in words if float(w.attrib["yMin"]) > 350]
    title = [w for w in footer if w.text not in {"1", "/"}]
    extracted = " ".join(w.text or "" for w in title)
    assert "PREFIXMARKER" in extracted.upper() and "…" in extracted, extracted
    counter = next(w for w in footer if w.text == "1")
    assert max(float(w.attrib["xMax"]) for w in title) + 2 <= float(
        counter.attrib["xMin"]
    )
    assert max(float(w.attrib["yMax"]) for w in footer) <= 408.18896
    if font:
        fonts = subprocess.run(
            ["pdffonts", "main.pdf"], check=True, capture_output=True, text=True
        ).stdout
        assert font in fonts, fonts
    if "fill:" in wrapper:
        subprocess.run(
            ["pdftocairo", "-svg", "main.pdf", "footer.svg"],
            check=True,
            capture_output=True,
        )
        assert "100%,0%,0%" in Path("footer.svg").read_text().replace(" ", "")
    if "link" in wrapper:
        assert b"https://example.com" in Path("main.pdf").read_bytes()


@pytest.mark.parametrize(
    "title",
    [
        r"Alpha \ Beta",
        r"Alpha \ Beta \ Gamma",
        "Alpha\n\nBeta\n\nGamma",
        '#box(height: 40pt, fill: rgb("ff0000"))[Boxmarker] After',
        '#image("tall.svg", height: 40pt) After',
    ],
)
@pytest.mark.parametrize("option", ["title", "short-title"])
def test_footer_is_one_line_with_tall_content(project, title, option):
    Path("tall.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="40"><rect width="10" height="40" fill="red"/></svg>'
    )
    result = compile_source(
        project + f"#show: slides.with({option}: [{title}])\n#slide()[Body]"
    )
    assert result.returncode == 0, result.stderr
    footer = [w for w in pdf_words() if float(w.attrib["yMin"]) > 350]
    text = " ".join(w.text or "" for w in footer)
    for marker in (
        ["Boxmarker", "After"]
        if "box" in title
        else ["After"]
        if "image" in title
        else ["Alpha", "Beta"] + (["Gamma"] if "Gamma" in title else [])
    ):
        assert marker in text, text
    assert (
        max(float(w.attrib["yMax"]) for w in footer)
        - min(float(w.attrib["yMin"]) for w in footer)
        <= 11
    )
    assert max(float(w.attrib["yMax"]) for w in footer) <= 408.18896
    last_page = str(len(pdf_text().rstrip("\n\f").split("\f")))
    subprocess.run(
        [
            "pdftocairo",
            "-svg",
            "-f",
            last_page,
            "-l",
            last_page,
            "main.pdf",
            "footer.svg",
        ],
        check=True,
        capture_output=True,
    )
    root = ET.parse("footer.svg").getroot()
    # No image/box can be laid out below the page; the red image is bounded too.
    if "image" in title or "box" in title:
        red = next(
            n
            for n in root.iter()
            if "100%,0%,0%" in n.attrib.get("fill", "").replace(" ", "")
        )
        coords = [float(x) for x in re.findall(r"[-+]?\d+(?:\.\d+)?", red.attrib["d"])]
        ys = coords[1::2]
        assert max(ys) - min(ys) <= 11 and max(ys) <= 408.18896


@pytest.mark.parametrize("bound", [False, True])
def test_empty_yaml_register_has_clear_error(project, bound):
    Path("glossary.yaml").write_text("")
    setup = (
        '#let g = glossary-tools(yaml("/glossary.yaml"))\n#show: g.setup'
        if bound
        else '#show: glossary-setup.with(yaml("/glossary.yaml"))'
    )
    result = compile_source(project + setup + "\n#glossary()")
    assert result.returncode != 0 and "empty glossary register" in result.stderr, (
        result.stderr
    )


@pytest.mark.parametrize(
    "wrapper",
    [
        "underline",
        "highlight",
        "strike",
        "overline",
        "super",
        "sub",
        "box",
        "raw",
        "math",
        "pad",
    ],
)
@pytest.mark.parametrize("mixed", [False, True])
def test_generic_footer_prefix(project, wrapper, mixed):
    value = "Prefixmarker" + " extended research area facility" * 30
    if wrapper == "raw":
        title = f'#raw("{value}")'
    elif wrapper == "math":
        title = "$" + "x+" * 250 + "x$"
    elif wrapper == "pad":
        assert "pad" not in (ASSETS / "devkit-docs/slides.typ").read_text()
        title = f"#pad(left: 1pt, right: 1pt)[{value}]"
    else:
        title = f"#{wrapper}[{value}]"
    if mixed:
        title = "Intro " + title + " After"
    result = compile_source(
        project + f"#show: slides.with(short-title: [{title}])\n#slide()[Body]"
    )
    assert result.returncode == 0, result.stderr
    footer = [w for w in pdf_words() if float(w.attrib["yMin"]) > 350]
    title_words = [w for w in footer if w.text not in {"1", "/"}]
    extracted = " ".join(w.text or "" for w in title_words)
    assert "…" in extracted, extracted
    assert ("Prefixmarker" if wrapper != "math" else "□") in extracted, extracted
    if mixed:
        assert "Intro" in extracted, extracted
    counter = next(w for w in footer if w.text == "1")
    assert max(float(w.attrib["xMax"]) for w in title_words) + 2 <= float(
        counter.attrib["xMin"]
    )


def test_oversized_footer_measures_rendered_prefix(project):
    result = compile_source(
        project
        + "#show: slides.with(short-title: text(size: 40pt)[Prefixmarker extended research area facility "
        + "extended research area facility " * 30
        + "])\n#slide()[Body]"
    )
    assert result.returncode == 0, result.stderr
    footer = [
        w
        for w in pdf_words()
        if float(w.attrib["yMin"]) > 350 and w.text not in {"1", "/"}
    ]
    extracted = " ".join(w.text or "" for w in footer)
    assert "Prefixmarker" in extracted and "…" in extracted, extracted
    assert (
        max(float(w.attrib["xMax"]) for w in footer)
        - min(float(w.attrib["xMin"]) for w in footer)
        > 130
    )


def test_rtl_footer_ellipsis_at_cut_end(project):
    result = compile_source(
        project
        + '#set text(lang: "he", dir: rtl)\n#show: slides.with(short-title: ['
        + "שלום עולם " * 100
        + "])\n#slide()[Body]"
    )
    assert result.returncode == 0, result.stderr
    footer = [w for w in pdf_words() if float(w.attrib["yMin"]) > 350]
    ellipsis = next(w for w in footer if "…" in (w.text or ""))
    hebrew = [
        w for w in footer if any("\u0590" <= c <= "\u05ff" for c in (w.text or ""))
    ]
    assert hebrew
    assert float(ellipsis.attrib["xMax"]) <= min(
        float(w.attrib["xMin"]) for w in hebrew
    )
