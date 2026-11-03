"""Compiler-independent checks for the Typst-aware source scanner."""

from vig_utils.typst_content import blank, fallback_width, instrument, tokens


def test_strings_nested_comments_and_raw_examples():
    source = '/* outer /* nested */ text */ "#set page()" `#set page()`\n#set text(font: "Example")'
    assert [word for word, _, _ in tokens(source)].count("set") == 1
    origins = {}
    instrument(source, "main.typ", origins)
    assert origins["bypasses"] == [("main.typ", 2, set())]


def test_marker_must_be_a_comment():
    origins = {}
    instrument('#figure(rect(), alt: "// figure-caption: ignore")', "a.typ", origins)
    assert next(iter(origins.values()))[2] == set()


def test_visible_opaque_and_blank_formatting_content():
    assert blank({"func": "hide", "body": {"func": "text", "text": "X"}})
    assert blank({"func": "strong", "body": {"func": "text", "text": " \u200b"}})
    assert not blank({"func": "ref", "target": "sec"})
    assert not blank({"func": "equation", "body": {"func": "text", "text": "x"}})


def test_unresolved_width_and_page_margin():
    assert fallback_width({"width": "5em"}, None, 100) is None
    assert (
        fallback_width(
            {"width": "50% + 0pt"}, {"width": "100pt", "margin": "0% + 20pt"}, 100
        )
        == 30
    )


def test_settings_and_prose_are_not_rewritten_as_calls():
    source = "#set figure(gap: 10pt)\nA prose example: figure(example)."
    assert instrument(source, "a.typ", {}) == source


def test_svg_css_specificity(tmp_path):
    from vig_utils.typst_content import svg_text

    path = tmp_path / "chart.svg"
    path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50"><style>#small {font-size:5px} .large {font-size:20px}</style><text id="small" class="large">Text</text></svg>'
    )
    assert svg_text(path)[0] == 5


def test_nested_font_feature_is_not_a_family_override():
    origins = {}
    source = '#set text(features: (font: 1))\n#set text(font: "Libertinus Serif")'
    instrument(source, "a.typ", origins)
    assert origins["bypasses"] == [("a.typ", 2, set())]
