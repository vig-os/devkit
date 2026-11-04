"""Compiler-independent checks for the Typst-aware source scanner."""

from vig_utils.typst_content import blank, fallback_width, instrument, tokens


def test_strings_nested_comments_and_raw_examples():
    source = '/* outer /* nested */ text */ #let quoted = "#set page()" `#set page()`\n#set text(font: "Example")'
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


def test_existing_dotted_labels_are_preserved():
    origins = {}
    instrument("#figure(rect()) <fig.example>", "a.typ", origins)
    assert "<fig.example>" in origins


def test_relative_plus_absolute_width():
    assert (
        fallback_width(
            {"width": "50% + 10pt"}, {"width": "100pt", "margin": "20pt"}, 100
        )
        == 40
    )


def test_svg_em_percent_viewbox_and_tail_text(tmp_path):
    from vig_utils.typst_content import svg_text

    path = tmp_path / "chart.svg"
    for attributes, text, expected in [
        ('font-size="20"', '<tspan font-size="0.5em">X</tspan>', 10),
        ('font-size="20"', '<tspan font-size="50%">X</tspan>', 10),
        ('font-size="5"', '<tspan font-size="20">Big</tspan>tiny', 5),
    ]:
        path.write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100" viewBox="0 0 100 50"><text {attributes}>{text}</text></svg>'
        )
        smallest, canvas, _ = svg_text(path)
        assert smallest == expected
        assert canvas == 100


def test_svg_unused_defs_and_hidden_styles(tmp_path):
    from vig_utils.typst_content import svg_text

    path = tmp_path / "chart.svg"
    path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50"><defs><text id="tiny" font-size="1">Unused</text></defs><text style="display:none;font-size:2px">Hidden</text><g style="visibility:hidden"><text font-size="3">Hidden</text></g><text font-size="10">Visible</text></svg>'
    )
    assert svg_text(path)[0] == 10
    path.write_text(path.read_text().replace("</svg>", '<use href="#tiny"/></svg>'))
    assert svg_text(path)[0] == 1


def test_svg_entities_remain_forbidden(tmp_path):
    import pytest
    from vig_utils.typst_content import svg_text

    path = tmp_path / "entity.svg"
    path.write_text(
        '<!DOCTYPE svg [<!ENTITY example "text">]><svg xmlns="http://www.w3.org/2000/svg" width="100"><text>&example;</text></svg>'
    )
    with pytest.raises(ValueError):
        svg_text(path)


def test_font_shorthand_cascade_and_unresolved(tmp_path):
    import pytest
    from vig_utils.typst_content import svg_text

    path = tmp_path / "fonts.svg"
    cases = [
        (
            "<text style=\"font: italic small-caps 700 5px/1.2 'DejaVu Sans'\">x</text>",
            5,
        ),
        ("<style>text {font: 5px sans-serif}</style><text>x</text>", 5),
        (
            '<style>#x {font-size:20px}</style><text id="x" style="font:5px sans-serif">x</text>',
            5,
        ),
        (
            '<style>text {font:5px sans-serif !important}</style><text style="font-size:20px">x</text>',
            5,
        ),
        (
            '<style>#x {font-size:20px!important}</style><text id="x" style="font:5px sans-serif!important">x</text>',
            5,
        ),
        ('<text style="font:20px sans-serif;font-size:5px">x</text>', 5),
        ('<text style="font-size:20px;font:5px sans-serif">x</text>', 5),
    ]
    for body, expected in cases:
        path.write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50">{body}</svg>'
        )
        assert svg_text(path)[0] == expected
    for value in ("caption", "bold var(--size) sans-serif", "medium sans-serif"):
        path.write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50"><text style="font:{value}">x</text></svg>'
        )
        with pytest.raises(ValueError, match="font"):
            svg_text(path)


def test_svg_nested_viewports_symbols_and_zero_text(tmp_path):
    from vig_utils.typst_content import svg_text

    path = tmp_path / "viewports.svg"
    for body in (
        '<svg width="50" height="25" viewBox="0 0 100 50"><text font-size="10">x</text></svg>',
        '<defs><symbol id="plot" viewBox="0 0 100 50"><text font-size="10">x</text></symbol></defs><use href="#plot" width="50" height="25"/>',
    ):
        path.write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50">{body}<text font-size="0">invisible</text></svg>'
        )
        assert svg_text(path)[0] == 5


def test_svg_use_expansion_is_bounded(tmp_path):
    import pytest
    from vig_utils.typst_content import svg_text

    path = tmp_path / "use.svg"
    definitions = '<text id="a0" font-size="10">x</text>' + "".join(
        f'<g id="a{i}"><use href="#a{i - 1}"/><use href="#a{i - 1}"/></g>'
        for i in range(1, 15)
    )
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50"><defs>{definitions}</defs><use href="#a14"/></svg>'
    )
    with pytest.raises(ValueError, match="limit"):
        svg_text(path)


def test_unknown_image_cannot_borrow_unrelated_path_suppression():
    from vig_utils.typst_content import image_rows

    origins = {
        "image_calls": [
            {
                "id": "<x>",
                "origin": ("main.typ", 1, {"figure-text-size"}),
                "raw": None,
                "path": None,
            }
        ]
    }
    rows = [
        {
            "func": "metadata",
            "value": {
                "kind": "devkit-source-image",
                "element": {"source": 'path("/other/logo.svg")'},
                "page": {},
            },
        }
    ]
    assert image_rows(rows, origins, {"main.typ"})[0].get("label") is None


def test_shorthand_em_inherit_and_uppercase_important(tmp_path):
    from vig_utils.typst_content import svg_text

    path = tmp_path / "font-coverage.svg"
    cases = [
        ('<g font-size="20"><text style="font:0.5em sans-serif">x</text></g>', 10),
        ('<g font-size="20"><text style="font:inherit">x</text></g>', 20),
        ('<g font-size="20"><text style="font-size:inherit">x</text></g>', 20),
        (
            '<style>text {font:5px sans-serif !IMPORTANT}</style><text style="font-size:20px">x</text>',
            5,
        ),
        (
            '<style>#x {font-size:20px!important}</style><text id="x" style="font:5px sans-serif !IMPORTANT">x</text>',
            5,
        ),
    ]
    for body, expected in cases:
        path.write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50">{body}</svg>'
        )
        assert svg_text(path)[0] == expected


def test_svg_use_work_is_bounded_by_visited_nodes(tmp_path, monkeypatch):
    import pytest
    from vig_utils import typst_svg

    path = tmp_path / "many-texts.svg"
    path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50"><defs><g id="plot">'
        + '<text font-size="10">x</text>' * 10000
        + "</g></defs>"
        + '<use href="#plot"/>' * 400
        + "</svg>"
    )
    original = typst_svg.SvgText.visit
    visited = 0

    def visit(*args, **kwargs):
        nonlocal visited
        visited += 1
        assert visited <= 100000, "SVG walker exceeded the bounded-work canary"
        return original(*args, **kwargs)

    monkeypatch.setattr(typst_svg.SvgText, "visit", visit)
    with pytest.raises(ValueError, match="limit"):
        typst_svg.svg_metrics(path)


def test_real_code_blocks_remain_instrumented():
    from vig_utils.typst_content import call_spans

    for source in (
        "#(figure(rect()))",
        "#{ figure(rect()) }",
        "#if true { figure(rect()) }",
        "#for n in range(1) { figure(rect()) }",
    ):
        assert [call[0] for call in call_spans(source)] == ["figure"]


def test_inline_calls_keep_native_argument_code_and_markup_captions():
    from vig_utils.typst_content import call_spans

    source = '#figure(image("chart.svg"), caption: [see table(s)])'
    assert [call[0] for call in call_spans(source)] == ["figure", "image"]


def test_dependency_tokens_are_cached_across_call_orders(monkeypatch):
    from vig_utils import typst_content

    source = '#include "part.typ"\n#figure(image("chart.svg"), caption: [Chart])'
    origins = {}
    instrument(source, "main.typ", origins)
    context = {
        "origins": origins,
        "originals": {"main.typ": source, "part.typ": "Hello"},
    }
    original = typst_content.tokens
    seen = []

    def tokenize(text, *args, **kwargs):
        seen.append(text)
        return original(text, *args, **kwargs)

    monkeypatch.setattr(typst_content, "tokens", tokenize)
    for kind in ("figure_calls", "image_order", "call_order"):
        typst_content.ordered_calls("main.typ", context, {"main.typ", "part.typ"}, kind)
    assert seen.count(source) == 1
    assert seen.count("Hello") == 1


def test_qualified_inline_call_arguments_keep_code_but_following_prose_does_not():
    from vig_utils.typst_content import call_spans

    source = '#helper.identity(figure(image("chart.svg"), caption: [see table(s)])) figure(rect())'
    assert [call[0] for call in call_spans(source)] == ["figure", "image"]


def test_else_blocks_and_chains_keep_code_across_lines():
    from vig_utils.typst_content import call_spans

    for source in (
        "#if false {\n []\n} else {\n table([a])\n}",
        "#if false {\n []\n} else if false {\n []\n} else {\n table([a])\n}",
        "#let conf(doc) = if false {\n doc\n} else {\n set page(margin: 1cm)\n doc\n}",
        "#context {\n table([a])\n}",
    ):
        assert [call[0] for call in call_spans(source)] == [
            "set" if "set page" in source else "table"
        ]


def test_markup_quotes_urls_and_escaped_hash_do_not_hide_code():
    from vig_utils.typst_content import call_spans

    for prose in (
        'A 27" monitor.',
        "https://example.com/#table([fake])",
        r"\#set page(margin: 1cm)",
    ):
        assert [call[0] for call in call_spans(prose + "\n#table([a])")] == ["table"]


def test_qualified_builtin_calls_are_instrumented_from_their_root():
    from vig_utils.typst_content import call_spans

    source = "#std.table([a])\n#std.figure(rect())"
    calls = list(call_spans(source))
    assert [call[0] for call in calls] == ["table", "figure"]
    rewritten = instrument(source, "a.typ", {})
    assert "#std.[#(" not in rewritten
    assert rewritten.count("std.") == 2


def test_content_is_markup_even_in_statement_and_adjacency_matters():
    from vig_utils.typst_content import call_spans

    for source in (
        "#let a = [table([a])]",
        "#identity (table([a]))",
        "#context [table([a])]",
    ):
        assert list(call_spans(source)) == []


def test_logo_direct_form_and_closing_line_suppression():
    for name in ("devkit-document", "devkit-document.with"):
        origins = {}
        instrument(
            f'#{name}(\n logo: "logo.svg"\n) // figure-text-size: ignore',
            "a.typ",
            origins,
        )
        assert origins["image_calls"][0]["logo"]
        assert origins["image_calls"][0]["origin"][2] == {"figure-text-size"}


def test_instrument_tokenizes_source_once(monkeypatch):
    from vig_utils import typst_content

    source = "#figure(rect())"
    original, seen = typst_content.tokens, []

    def tokenize(text, *args, **kwargs):
        seen.append(text)
        return original(text, *args, **kwargs)

    monkeypatch.setattr(typst_content, "tokens", tokenize)
    instrument(source, "a.typ", {})
    assert seen.count(source) == 1


def test_unclosed_css_rule_warns(tmp_path):
    import pytest
    from vig_utils.typst_svg import svg_metrics

    path = tmp_path / "chart.svg"
    path.write_text(
        '<svg viewBox="0 0 100 50"><style>text {font-size:5px</style><text>x</text></svg>'
    )
    with pytest.raises(ValueError, match="CSS"):
        svg_metrics(path)


def test_css_rule_work_is_bounded(tmp_path, monkeypatch):
    import pytest
    from vig_utils import typst_svg

    path = tmp_path / "chart.svg"
    path.write_text(
        '<svg viewBox="0 0 100 50"><style>'
        + "text {font-size:10px}" * 20000
        + "</style>"
        + "<text>x</text>" * 30000
        + "</svg>"
    )
    original, calls = typst_svg.svg_style, 0

    def style(*args):
        nonlocal calls
        calls += 1
        assert calls < 100, "CSS work exceeded the bounded-work canary"
        return original(*args)

    monkeypatch.setattr(typst_svg, "svg_style", style)
    with pytest.raises(ValueError, match="CSS.*limit"):
        typst_svg.svg_metrics(path)


def test_svg_reference_depth_is_bounded(tmp_path):
    import pytest
    from vig_utils.typst_svg import svg_metrics

    path = tmp_path / "depth.svg"
    definitions = '<text id="a0">x</text>' + "".join(
        f'<g id="a{i}"><use href="#a{i - 1}"/></g>' for i in range(1, 33)
    )
    path.write_text(
        f'<svg viewBox="0 0 100 50"><defs>{definitions}</defs><use href="#a32"/></svg>'
    )
    with pytest.raises(ValueError, match="depth limit"):
        svg_metrics(path)


def test_prose_quote_before_code_string_and_url_fragment():
    from vig_utils.typst_content import call_spans

    assert [
        call[0]
        for call in call_spans('A 27" monitor.\n#set text(font: "New Computer Modern")')
    ] == ["set"]
    assert [
        call[0] for call in call_spans("https://example.com/#fake #table([a])")
    ] == ["table"]


def test_css_budget_counts_repeated_reference_visits(tmp_path, monkeypatch):
    import pytest
    from vig_utils import typst_svg

    path = tmp_path / "reused.svg"
    path.write_text(
        '<svg viewBox="0 0 100 50"><style>'
        + "text {font-size:10px}" * 1000
        + '</style><defs><g id="plot">'
        + "<text>x</text>" * 100
        + "</g></defs>"
        + '<use href="#plot"/>' * 20
        + "</svg>"
    )
    original, calls = typst_svg.svg_style, 0

    def style(*args):
        nonlocal calls
        calls += 1
        assert calls <= 1000, "CSS work exceeded the bounded-work canary"
        return original(*args)

    monkeypatch.setattr(typst_svg, "svg_style", style)
    with pytest.raises(ValueError, match="CSS.*limit"):
        typst_svg.svg_metrics(path)
