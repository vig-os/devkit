"""Real compiler acceptance tests for content helpers (#1994)."""

import json
import os
import subprocess
import time
import tomllib
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


def compile_source(source, *inputs, timeout=None):
    Path("main.typ").write_text("// devkit: entry\n" + source)
    return subprocess.run(
        [
            "typst",
            "compile",
            "--root",
            ".",
            "--ignore-system-fonts",
            "--font-path",
            os.environ.get(
                "DEVKIT_TYPST_TEST_FONTS",
                str(Path(__file__).resolve().parent / "fixtures/typst-fonts"),
            ),
            "--jobs",
            "2",
            *inputs,
            "main.typ",
            "main.pdf",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
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


def pdf_words(*, last_page=False):
    result = subprocess.run(
        ["pdftotext", "-bbox", "main.pdf", "-"],
        check=True,
        capture_output=True,
        text=True,
    )
    root = ET.fromstring(result.stdout)
    if last_page:
        root = list(root.iter("{http://www.w3.org/1999/xhtml}page"))[-1]
    return list(root.iter("{http://www.w3.org/1999/xhtml}word"))


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
    "value,expected",
    [
        (f"#{wrapper}[Prefixmarker]", "Prefixmarker")
        for wrapper in (
            "strong",
            "emph",
            "underline",
            "highlight",
            "strike",
            "overline",
            "smallcaps",
            "super",
            "sub",
            "box",
            "block",
            "quote",
            "heading",
        )
    ]
    + [
        ("#text(fill: red)[Prefixmarker]", "Prefixmarker"),
        ("#text(size: 40pt)[Prefixmarker]", "Prefixmarker"),
        ("#rect[Hidden] Prefixmarker", "Prefixmarker"),
        ('#link("https://example.com")[Prefixmarker]', "Prefixmarker"),
        ('#raw("Prefixmarker")', "Prefixmarker"),
        ("$alpha$", "α"),
        ("$dif A$", "d A"),
        ("$vec(x,y)$", "x y"),
        ("$sum_(i=1)^n x_i$", "∑ n i=1 x i"),
        ("#stack([Prefixmarker], [Second])", "Prefixmarker Second"),
        ("#grid([Prefixmarker], [Second])", "Prefixmarker Second"),
        ("#table([Prefixmarker], [Second])", "Prefixmarker Second"),
        ("#emph[Prefixmarker] <label>", "Prefixmarker"),
        ("#enum.item[Prefixmarker]", "Prefixmarker"),
        ("#columns(2)[Prefixmarker]", "Prefixmarker"),
        ("Prefixmarker#footnote[Hidden]", "Prefixmarker"),
        ("Prefixmarker#place[Hidden]", "Prefixmarker"),
        ("#rotate(20deg)[Prefixmarker]", "Prefixmarker"),
        ("#move(dx: 2pt)[Prefixmarker]", "Prefixmarker"),
        ('"Prefixmarker"', "“Prefixmarker”"),
        (r"Prefixmarker \ Second", "Prefixmarker Second"),
        ("Prefixmarker\n\nSecond", "Prefixmarker Second"),
        ('#image("tall.svg", height: 40pt) Prefixmarker', "Prefixmarker"),
        ("漢字" * 100, "漢字"),
        ("☺" * 100, "☺"),
        ("A" * 400, "AAAA"),
    ],
)
@pytest.mark.parametrize("option", ["title", "short-title"])
def test_plain_footer_prefix_and_bounds(project, value, expected, option):
    Path("tall.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="40"/>'
    )
    result = compile_source(
        project
        + f"#show: slides.with({option}: [{value} extended research area facility "
        + "extended research area facility " * 30
        + "])\n#slide()[Body]"
    )
    assert result.returncode == 0, result.stderr
    # Check the content page independently of the optional title slide.
    footer = [w for w in pdf_words(last_page=True) if float(w.attrib["yMin"]) > 350]
    title = [w for w in footer if w.text != "/" and not (w.text or "").isdigit()]
    extracted = " ".join(w.text or "" for w in title)
    assert extracted.startswith(expected) and extracted.endswith("…"), extracted
    assert "Hidden" not in extracted
    counter = next(w for w in footer if (w.text or "").isdigit())
    assert max(float(w.attrib["xMax"]) for w in title) + 2 * 72 / 25.4 <= float(
        counter.attrib["xMin"]
    )
    assert min(float(w.attrib["xMin"]) for w in title) >= 12 * 72 / 25.4 - 0.1
    assert max(float(w.attrib["yMax"]) for w in footer) <= 144 * 72 / 25.4
    assert (
        max(float(w.attrib["yMax"]) for w in footer)
        - min(float(w.attrib["yMin"]) for w in footer)
        <= 11
    )
    subprocess.run(
        ["pdftohtml", "-xml", "-zoom", "1", "main.pdf", "footer.xml"],
        check=True,
        capture_output=True,
    )
    root = ET.parse("footer.xml")
    fonts = {n.attrib["id"]: n.attrib for n in root.iter("fontspec")}
    for node in list(root.iter("page"))[-1].iter("text"):
        if float(node.attrib["top"]) > 350:
            spec = fonts[node.attrib["font"]]
            assert float(spec["size"]) == 9
            assert spec["color"] == "#000000"
            assert "Bold" not in spec["family"] and "Italic" not in spec["family"]
            assert node.find("b") is None and node.find("i") is None


@pytest.mark.parametrize("option", ["title", "short-title"])
@pytest.mark.parametrize(
    "value,expected",
    [
        ("", ""),
        ("Short", "Short"),
        ("$alpha$", "α"),
        ("#rect()", "□"),
        ("$#h(1pt)$", "□"),
    ],
)
def test_plain_footer_short_and_empty(project, option, value, expected):
    result = compile_source(
        project + f"#show: slides.with({option}: [{value}])\n#slide()[Body]"
    )
    assert result.returncode == 0, result.stderr
    # Inspect the last page, excluding any title slide.
    words = pdf_words()
    footer = [w.text or "" for w in words if float(w.attrib["yMin"]) > 350]
    assert (
        footer.count(expected) == (2 if option == "title" else 1)
        if expected
        else "…" not in footer
    )


def test_plain_footer_rtl_bounds(project):
    result = compile_source(
        project
        + '#set text(lang: "he", dir: rtl)\n#show: slides.with(short-title: ['
        + "שלום עולם " * 100
        + "])\n#slide()[Body]"
    )
    assert result.returncode == 0, result.stderr
    footer = [w for w in pdf_words() if float(w.attrib["yMin"]) > 350]
    title = [
        w
        for w in footer
        if any("\u0590" <= c <= "\u05ff" for c in (w.text or ""))
        or "…" in (w.text or "")
    ]
    assert title
    assert min(float(w.attrib["xMin"]) for w in title) >= 12 * 72 / 25.4 - 0.1
    counter = next(w for w in footer if (w.text or "").isdigit())
    assert max(float(w.attrib["xMax"]) for w in title) <= (256 - 12) * 72 / 25.4 + 0.1
    assert (
        min(float(w.attrib["xMin"]) for w in title)
        >= float(counter.attrib["xMax"]) + 2 * 72 / 25.4
    )
    ellipsis = next(w for w in title if "…" in (w.text or ""))
    assert float(ellipsis.attrib["xMin"]) == min(float(w.attrib["xMin"]) for w in title)


@pytest.mark.parametrize(
    "value", ["none", "42", "(a: [Hidden])", "([A], 42, (x: [Hidden]), [B])", "<label>"]
)
def test_footer_extractor_ignores_unknown_field_shapes(project, value):
    expected = "AB" if value.startswith("([A]") else ""
    result = compile_source(
        project + f'#assert.eq(slides.footer-text({value}), "{expected}")'
    )
    assert result.returncode == 0, result.stderr


def test_footer_short_title_overrides_title_and_skips_effects(project):
    result = compile_source(
        project
        + """#show: slides.with(title: [Deckmarker], short-title: [Shortmarker#footnote[Hidden]#metadata([Hidden])#context[Hidden]#context counter(page).display()#state("footer").update([Hidden])#place[Hidden]])
#slide()[Body]
"""
    )
    assert result.returncode == 0, result.stderr
    footer = [w.text for w in pdf_words() if float(w.attrib["yMin"]) > 350]
    assert footer.count("Shortmarker") == 2
    assert "Deckmarker" not in footer and "Hidden" not in pdf_text()


@pytest.mark.parametrize("option", ["title", "short-title"])
def test_footer_deep_sequences_are_iterative(project, option):
    result = compile_source(
        project
        + """#let nest(n, f) = {
  let result = [Endmarker]
  for _ in range(n) { result = f(result) }
  result
}
#let nested = nest(200, c => [x#c])
#assert.eq(slides.footer-text(nested), "x" * 200 + "Endmarker")
"""
        + f"#show: slides.with({option}: nested)\n#slide()[Body]"
    )
    assert result.returncode == 0, result.stderr
    footer = [w for w in pdf_words(last_page=True) if float(w.attrib["yMin"]) > 350]
    title = next(w for w in footer if (w.text or "").startswith("xxxxx"))
    assert (title.text or "").endswith("…")
    counter = next(w for w in footer if (w.text or "").isdigit())
    assert float(title.attrib["xMax"]) + 2 * 72 / 25.4 <= float(counter.attrib["xMin"])


@pytest.mark.parametrize(
    "value,expected",
    [
        ("[Before#hide[Hidden] After]", "Before After"),
        ("terms.item([Term], [Desc])", "Term: Desc"),
        ("[A#h(1cm)B]", "A B"),
        ("[A#h(0pt)B]", "AB"),
        ("[A#h(0em)B]", "AB"),
        ("[A#h(0%)B]", "AB"),
        ("[A#h(1fr)B]", "A B"),
        ("grid([A1], [B2])", "A1 B2"),
        ("table([A1], [B2])", "A1 B2"),
        ("stack([A1], 1cm, [B2])", "A1 B2"),
        ("[$mat(1,2;3,4)$]", "1 2 3 4"),
        ("[$x_1^2$]", "x 2 1"),
        ("[$vec(x,y)$]", "x y"),
        ("[A $#h(1pt)$ B]", "A □ B"),
        ('["One" "Two"]', "“One” “Two”"),
        ("['Single']", "‘Single’"),
        ("[\"Outer 'inner' words\"]", "“Outer ‘inner’ words”"),
    ],
)
def test_footer_plain_leaf_separators_and_quotes(project, value, expected):
    result = compile_source(
        project
        + f"#assert.eq(slides.footer-text({value}), {json.dumps(expected, ensure_ascii=False)})"
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("kind", ["table", "grid"])
def test_footer_separates_grouped_cells(project, kind):
    value = f"{kind}({kind}.header([A1], [B2]), [C3], {kind}.footer([D4], [E5]))"
    result = compile_source(
        project + f'#assert.eq(slides.footer-text({value}), "A1 B2 C3 D4 E5")'
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "value,prefix",
    [
        ("range(5000).map(_ => [Prefixword ]).join()", "Prefixword Prefixword"),
        ("{ let c = [Endmarker]; for _ in range(1000) { c = [a #c b] }; c }", "a a a"),
        ("range(3000).map(_ => emph[Emphword ]).join()", "Emphword Emphword"),
        ('[#("Research " * 10000)]', "Research Research"),
    ],
    ids=["5000-children", "1000-levels", "3000-emphasised-words", "10000-words"],
)
def test_footer_large_titles_are_bounded_and_fast(project, value, prefix):
    started = time.monotonic()
    result = compile_source(
        project
        + f"#let value = {value}\n"
        + f'#assert(slides.footer-text(value).starts-with("{prefix}"))\n'
        + "#assert(slides.footer-text(value).clusters().len() <= 400)\n"
        + '#assert(slides.footer-text(value).ends-with("…"))\n'
        + "#show: slides.with(short-title: value)\n#slide()[Body]",
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert time.monotonic() - started < 30
    title = [
        w.text or ""
        for w in pdf_words(last_page=True)
        if float(w.attrib["yMin"]) > 350
        and w.text != "/"
        and not (w.text or "").isdigit()
    ]
    extracted = " ".join(title)
    assert extracted.startswith(prefix) and extracted.endswith("…"), extracted


def test_footer_for_loop_handles_many_skipped_children(project):
    result = compile_source(
        project
        + "#let value = [#range(15000).map(_ => hide[Hidden]).join()Prefixmarker]\n"
        + '#assert.eq(slides.footer-text(value), "Prefixmarker")',
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("count", [399, 400, 401])
def test_footer_cap_preserves_graphemes(project, count):
    cluster = "e\u0301"
    expected = cluster * count if count <= 400 else cluster * 399 + "…"
    result = compile_source(
        project
        + f"#assert.eq(slides.footer-text({json.dumps(cluster * count, ensure_ascii=False)}), {json.dumps(expected, ensure_ascii=False)})"
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "value,expected",
    [
        ("don't", "don’t"),
        ('It\'s the "best" plan', "It’s the “best” plan"),
        ("'Tis the 'season' rock'n'roll", "‘Tis the ‘season’ rock’n’roll"),
        ("1990's", "1990’s"),
    ],
)
def test_footer_apostrophes_match_typst_rendering(project, value, expected):
    result = compile_source(
        project
        + f"#let value = [{value}]\n"
        + f"#assert.eq(slides.footer-text(value), {json.dumps(expected, ensure_ascii=False)})\n"
        + "#show: slides.with(short-title: value)\n#slide()[#value]"
    )
    assert result.returncode == 0, result.stderr
    text = " ".join(pdf_text().split())
    assert text.count(expected) == 2, text


@pytest.mark.parametrize(
    "value,expected",
    [("[$cases(x,y)$]", "x y"), ("[A#v(1cm)B]", "A B"), ("[A#v(0pt)B]", "AB")],
)
def test_footer_cases_and_vertical_spacing(project, value, expected):
    result = compile_source(
        project + f'#assert.eq(slides.footer-text({value}), "{expected}")'
    )
    assert result.returncode == 0, result.stderr
