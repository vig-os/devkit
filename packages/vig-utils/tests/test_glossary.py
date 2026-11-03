"""Terminology register acceptance checks (#1994)."""

import json
import shutil
import subprocess
import time
from importlib.resources import files

import pytest
import yaml
from vig_utils import glossary


@pytest.fixture
def register(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init", "-q"], check=True)
    entries = [
        {
            "id": "pump",
            "term": "Feed Pump",
            "definition": "Moves fluid.",
            "kind": "part",
            "aliases": ["Supply Pump"],
            "forbidden": [{"term": "input pump", "use": "Feed Pump"}],
            "part-number": "FP-100",
            "pattern": r"FP-\d+",
        }
    ]
    (tmp_path / "glossary.yaml").write_text(yaml.safe_dump(entries))
    return tmp_path, entries


def test_valid_and_missing_register(register):
    root, _ = register
    assert glossary.main(["schema"]) == 0
    (root / "glossary.yaml").unlink()
    assert glossary.main(["schema"]) == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("kind", "device"),
        ("definition", None),
        ("status", "obsolete"),
        ("aliases", "alias"),
        ("forbidden", [{"term": "bad"}]),
        ("pattern", "["),
        ("extra", True),
    ],
)
def test_invalid_register(register, field, value):
    root, entries = register
    entries[0][field] = value
    (root / "glossary.yaml").write_text(yaml.safe_dump(entries))
    assert glossary.main(["schema"]) == 1


@pytest.mark.parametrize(
    "text,expected",
    [
        ("input pump", 1),
        ("INPUT PUMP", 1),
        ("input pumps", 0),
        ("preinput pump", 0),
        ("Supply Pump FP-100", 0),
        ("FP-101", 1),
        ("XFP-101", 0),
        ("FP-101X", 0),
        ("input pump // glossary: ignore", 0),
        ("input pump <!-- glossary: ignore -->", 1),
        ("input pump glossary: ignore", 1),
        ("// glossary: ignore\ninput pump", 1),
    ],
)
def test_terms(register, capsys, text, expected):
    root, _ = register
    (root / "source.typ").write_text(text)
    track(root)
    assert glossary.main(["terms"]) == expected
    if expected:
        error = capsys.readouterr().err
        assert "source.typ:" in error
        assert "Feed Pump" in error or "unregistered part" in error


def test_globs_generated_and_custom_register(register):
    root, _ = register
    (root / "custom.yaml").write_bytes((root / "glossary.yaml").read_bytes())
    (root / "glossary.yaml").unlink()
    (root / ".vig-os").write_text(
        'DEVKIT_GLOSSARY="custom.yaml"\nDEVKIT_GLOSSARY_SOURCES="docs/**"\n'
    )
    (root / "outside.md").write_text("input pump")
    (root / "docs/generated").mkdir(parents=True)
    (root / "docs/generated/out.md").write_text("input pump")
    track(root)
    assert glossary.main(["terms"]) == 0
    (root / "docs/in.md").write_text("input pump")
    track(root)
    assert glossary.main(["terms"]) == 1


def track(root):
    subprocess.run(["git", "add", "."], cwd=root, check=True)


def write_entries(root, entries):
    (root / "glossary.yaml").write_text(yaml.safe_dump(entries))


@pytest.mark.parametrize(
    "term,alias,bad,text,expected",
    [
        ("GitHub", "GitHub Hosting", "Github", "GitHub", 0),
        ("GitHub", "GitHub Hosting", "Github", "Github", 1),
        ("US", "United States", "us", "the US market", 0),
        ("US", "United States", "us", "contact us", 1),
        ("Feed Pump", "Supply Pump", "pump", "Feed Pump and Supply Pump", 0),
        ("Feed Pump", "Supply Pump", "pump", "feed pump and supply pump", 0),
        ("Feed Pump", "Supply Pump", "pump", "the pump", 1),
        ("Repository", "GitHub", "Github", "GitHub", 0),
        ("Repository", "GitHub", "Github", "Github", 1),
    ],
)
def test_registered_spans_and_casing(register, term, alias, bad, text, expected):
    root, entries = register
    entries[0].update(
        term=term, aliases=[alias], forbidden=[{"term": bad, "use": term}]
    )
    write_entries(root, entries)
    (root / "source.md").write_text(text)
    track(root)
    assert glossary.main(["terms"]) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("_input pump_", 1),
        ("__input pump__", 1),
        ("input\u00a0pump", 1),
        ("input\tpump", 1),
        ("input\npump", 1),
        ("input-pump", 0),
        ("`input pump`", 1),
        ("```\ninput pump\n```", 1),
    ],
)
def test_prose_whitespace_and_code(register, text, expected):
    root, _ = register
    (root / "source.md").write_text(text)
    track(root)
    assert glossary.main(["terms"]) == expected


@pytest.mark.parametrize(
    "suffix,marker,expected",
    [
        ("typ", "// glossary: ignore", 0),
        ("md", "<!-- glossary: ignore -->", 0),
        ("typ", "<!-- glossary: ignore -->", 1),
        ("md", "// glossary: ignore", 1),
        ("typ", "// glossary: ignore more text", 1),
        ("md", "<!-- glossary: ignore --> more text", 1),
        ("typ", "/* glossary: ignore */", 1),
    ],
)
def test_suppression_is_typed_and_at_line_end(register, suffix, marker, expected):
    root, _ = register
    (root / f"source.{suffix}").write_text(f"input pump {marker}\n")
    track(root)
    assert glossary.main(["terms"]) == expected


@pytest.mark.parametrize(
    "name", [".private/source.md", "generated/source.md", "data.yaml"]
)
def test_excluded_tracked_paths(register, name):
    root, _ = register
    (root / ".vig-os").write_text('DEVKIT_GLOSSARY_SOURCES="*"\n')
    path = root / name
    path.parent.mkdir(exist_ok=True)
    path.write_text("input pump")
    track(root)
    assert glossary.main(["terms"]) == 0


def test_only_tracked_files_and_no_implicit_non_git_fallback(register, capsys):
    root, _ = register
    (root / ".gitignore").write_text("node_modules/\nbuild/\n")
    for name in ("untracked.md", "node_modules/source.md", "build/source.md"):
        path = root / name
        path.parent.mkdir(exist_ok=True)
        path.write_text("input pump")
    assert glossary.main(["terms"]) == 0
    shutil.rmtree(root / ".git")
    assert glossary.main(["terms"]) == 1
    assert "Git" in capsys.readouterr().err


@pytest.mark.parametrize(
    "mutation",
    ["id", "term", "alias-term", "alias-forbidden", "use", "aliases", "empty-term"],
)
def test_schema_cross_entry_invariants(register, mutation):
    root, entries = register
    second = {
        "id": "second",
        "term": "Control Unit",
        "definition": "Controls.",
        "kind": "component",
    }
    entries.append(second)
    if mutation == "id":
        second["id"] = entries[0]["id"]
    elif mutation == "term":
        second["term"] = "feed pump"
    elif mutation == "alias-term":
        second["aliases"] = ["feed pump"]
    elif mutation == "alias-forbidden":
        second["aliases"] = ["input pump"]
    elif mutation == "use":
        entries[0]["forbidden"][0]["use"] = "Unknown"
    elif mutation == "aliases":
        second["aliases"] = ["Control", "Control"]
    else:
        second["term"] = ""
    write_entries(root, entries)
    assert glossary.main(["schema"]) == 1


def test_yaml_duplicate_keys_and_schema_identity(register):
    root, _ = register
    path = root / "glossary.yaml"
    path.write_text(path.read_text() + "  term: Another Pump\n")
    assert glossary.main(["schema"]) == 1
    schema = json.loads(files("vig_utils").joinpath("glossary.schema.json").read_text())
    assert schema["$id"].startswith("https://")


@pytest.mark.parametrize("configured", ["missing.yaml", "../outside.yaml"])
def test_configured_register_errors(register, configured):
    root, entries = register
    (root.parent / "outside.yaml").write_text(yaml.safe_dump(entries))
    (root / ".vig-os").write_text(f'DEVKIT_GLOSSARY="{configured}"\n')
    assert glossary.main(["schema"]) == 1


@pytest.mark.parametrize(
    "pattern", ["[", "(?z)FP-100", "FP-\\d*|", "(?:)", "OTHER-\\d+"]
)
def test_pattern_errors_name_entry(register, capsys, pattern):
    root, entries = register
    entries[0]["pattern"] = pattern
    write_entries(root, entries)
    assert glossary.main(["schema"]) == 1
    assert "pump" in capsys.readouterr().err


def test_inline_pattern_flags_and_part_deduplication(register, capsys):
    root, entries = register
    entries[0]["pattern"] = r"(?i)fp-\d+"
    entries.append(
        {
            "id": "family",
            "term": "Family",
            "definition": "Family.",
            "kind": "part",
            "pattern": r"FP-\d{3}",
        }
    )
    write_entries(root, entries)
    (root / "source.md").write_text("FP-101 https://example.com/FP-102")
    track(root)
    assert glossary.main(["schema"]) == 0
    assert glossary.main(["terms"]) == 1
    error = capsys.readouterr().err
    assert error.count("unregistered part 'FP-101'") == 1
    assert "FP-102" not in error


def test_part_known_sets_are_per_pattern(register, capsys):
    root, entries = register
    entries.append(
        {
            "id": "other",
            "term": "Other Pump",
            "definition": "Other.",
            "kind": "part",
            "pattern": r"FP-\d{3}",
            "part-number": "FP-101",
        }
    )
    write_entries(root, entries)
    (root / "source.md").write_text("FP-101")
    track(root)
    assert glossary.main(["terms"]) == 1
    assert "unregistered part" in capsys.readouterr().err


def test_non_utf8_names_file_and_continues_and_schema_never_scans(register, capsys):
    root, _ = register
    (root / "bad.md").write_bytes(b"\xff")
    (root / "source.md").write_text("input pump")
    track(root)
    assert glossary.main(["schema"]) == 0
    assert glossary.main(["terms"]) == 1
    error = capsys.readouterr().err
    assert "bad.md" in error and "UTF-8" in error and "source.md:1:" in error


def test_many_variants_timing_guard(register, monkeypatch):
    root, entries = register
    entries[0]["forbidden"] = [
        {"term": f"variant-{i:04}", "use": "Feed Pump"} for i in range(1000)
    ]
    write_entries(root, entries)
    (root / "source.md").write_text(
        "Ordinary neutral prose.\n" * 20000 + "variant-0999"
    )
    track(root)
    compiled = []
    real_compile = glossary.re.compile

    def record_compile(pattern, *args, **kwargs):
        if isinstance(pattern, str) and "variant" in pattern:
            compiled.append(pattern)
        return real_compile(pattern, *args, **kwargs)

    monkeypatch.setattr(glossary.re, "compile", record_compile)
    started = time.monotonic()
    assert glossary.main(["terms"]) == 1
    assert len(compiled) <= 2, "Compile one forbidden alternation per case mode"
    assert time.monotonic() - started < 10, "Terminology scanning exceeded 10 seconds"


@pytest.mark.parametrize("field,value", [("aliases", ["Same", "Same"]), ("term", "")])
def test_packaged_schema_constraints_independent_of_semantic_checks(
    register, field, value
):
    from jsonschema import Draft202012Validator

    _, entries = register
    entries[0][field] = value
    schema = json.loads(files("vig_utils").joinpath("glossary.schema.json").read_text())
    assert not Draft202012Validator(schema).is_valid(entries)


@pytest.mark.parametrize("name", ["Feed Pump", "Supply Pump", "Control Unit"])
def test_dead_forbidden_rules(register, name):
    root, entries = register
    entries.append(
        {
            "id": "control",
            "term": "Control Unit",
            "definition": "Controls.",
            "kind": "term",
        }
    )
    entries[0]["forbidden"] = [{"term": name, "use": "Feed Pump"}]
    write_entries(root, entries)
    assert glossary.main(["schema"]) == 1


@pytest.mark.parametrize(
    "text,bad,expected",
    [
        ("the Feed Pump", "the feed", 0),
        ("Feed Pump station", "pump station", 0),
        ("**Feed** Pump", "pump", 0),
        ("#strong[Feed] Pump", "pump", 0),
        ("ßßßßßßßßßß Feed Pump\npump", "pump", 1),
    ],
)
def test_protection_overlap_markup_and_offsets(register, text, bad, expected):
    root, entries = register
    entries[0]["forbidden"] = [{"term": bad, "use": "Feed Pump"}]
    write_entries(root, entries)
    (root / "source.md").write_text(text)
    track(root)
    assert glossary.main(["terms"]) == expected


@pytest.mark.parametrize(
    "term,bad,text", [("US", "us", "Us"), ("GitHub", "Github", "GITHUB")]
)
def test_case_sensitive_forbidden(register, term, bad, text):
    root, entries = register
    entries[0].update(term=term, aliases=[], forbidden=[{"term": bad, "use": term}])
    write_entries(root, entries)
    (root / "source.md").write_text(text)
    track(root)
    assert glossary.main(["terms"]) == 0


def test_overlapping_rules_keep_longest(register, capsys):
    root, entries = register
    entries[0]["forbidden"] = [
        {"term": t, "use": "Feed Pump"} for t in ("input", "input pump", "pump unit")
    ]
    write_entries(root, entries)
    (root / "source.md").write_text("input pump unit")
    track(root)
    assert glossary.main(["terms"]) == 1
    error = capsys.readouterr().err
    assert error.count("is forbidden") == 1
    assert "'input pump'" in error


def test_unsupported_sources_warn_and_utf8_path_once(register, capsys):
    root, _ = register
    (root / ".vig-os").write_text('DEVKIT_GLOSSARY_SOURCES="*.yaml,*.md"\n')
    (root / "bad.md").write_bytes(b"\xff")
    track(root)
    assert glossary.main(["terms"]) == 1
    error = capsys.readouterr().err
    assert "unsupported" in error and "*.yaml" in error
    assert error.count("bad.md") == 1


def test_candidates_precision_recall_and_source_selection(register, capsys):
    root, _ = register
    documents = {
        "source.md": "The Feed Pump uses Supply Pump and FP-100.\nThe Thermal Valve uses NASA and FlowController.\nSet flow_rate to AB-200.\nOrdinary prose starts here.\nThermal Valve supports NASA.\n",
        "source.typ": "#strong[Feed] Pump connects Control Unit.\n",
        "untracked.md": "WrongCandidate",
        "generated/out.md": "WrongCandidate",
    }
    for name, text in documents.items():
        path = root / name
        path.parent.mkdir(exist_ok=True)
        path.write_text(text)
    track(root)
    subprocess.run(["git", "reset", "-q", "--", "untracked.md"], check=True)
    assert glossary.main(["candidates"]) == 0
    rows = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    expected = {
        "Thermal Valve",
        "NASA",
        "FlowController",
        "flow_rate",
        "AB-200",
        "Control Unit",
    }
    actual = {row["candidate"] for row in rows}
    assert len(actual & expected) / len(actual) == 1.0  # precision
    assert len(actual & expected) / len(expected) == 1.0  # recall
    thermal = next(row for row in rows if row["candidate"] == "Thermal Valve")
    assert thermal["count"] == 2 and thermal["line"] == 2
    assert thermal["file"] == "source.md" and thermal["context"]
    assert thermal["nearest"] and 0 <= thermal["score"] <= 1
