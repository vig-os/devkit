"""Terminology register acceptance checks (#1994)."""

import pytest
import yaml
from vig_utils import glossary


@pytest.fixture
def register(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
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
        ("input pump <!-- glossary: ignore -->", 0),
        ("input pump glossary: ignore", 1),
        ("// glossary: ignore\ninput pump", 1),
    ],
)
def test_terms(register, capsys, text, expected):
    root, _ = register
    (root / "source.typ").write_text(text)
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
    assert glossary.main(["terms"]) == 0
    (root / "docs/in.md").write_text("input pump")
    assert glossary.main(["terms"]) == 1
