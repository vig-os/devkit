"""Real compiler acceptance tests for content helpers (#1994)."""

import json
import os
import subprocess
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
    result = compile_source(
        project
        + """#show: devkit-document.with()
#term("cpu"), #term("cpu"). #term("sample").
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
        project + "#show: slides.with(title: [Canonical])\n#slide()[Body #glossary()]"
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
    "label", ["#super[*]", "#sub(typographic: false)[2]", "$text(size: #4pt, x)$"]
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


def test_glossary_body_first_use_and_sorted_unique_appendix(project):
    project += '#show: glossary-setup.with(yaml("/glossary.yaml"))\n'
    result = compile_source(
        project
        + '\n#outline()\n#outline(target: figure)\n= Using #term("cpu")\n#fig(rect(), caption: [About #term("sample")])\n#term("sample"). #term("cpu").\n#glossary()'
    )
    assert result.returncode == 0, result.stderr
    text = " ".join(pdf_text().split())
    assert text.count("Using Central processing unit (CPU)") == 1, text
    assert text.count("Using CPU") == 1, text
    assert "A specimen. (Sample)" not in text
    appendix = text.split("Glossary")[-1]
    assert appendix.index("CPU") < appendix.index("Sample"), appendix
    assert appendix.count("Sample") == 1


@pytest.mark.parametrize("mode", ["plain", "compile", "canonical"])
def test_large_glossary_builds(project, mode):
    project += '#show: glossary-setup.with(yaml("/glossary.yaml"))\n'
    path = Path("glossary.yaml")
    path.write_text(path.read_text() + "#" + "padding" * 23000 + "\n")
    result = compile_source(project + '#term("sample")')
    assert result.returncode == 0, result.stderr
    if mode != "plain":
        from vig_utils import typst_guard

        assert typst_guard.main([mode]) == 0


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
