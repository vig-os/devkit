"""Document-repository canaries for the opt-in Typst surface (#1994)."""

import importlib
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init", "-q"], check=True)
    for name, source in {
        "main.typ": "// devkit: entry\nHello\n",
        "parts/body.typ": "Included content\n",
        "templates/plain.typ": "Template\n",
        "generated/cache.typ": '#error("ignored")\n',
        "library.typ": "#let title = [Title]\n",
    }.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
    subprocess.run(["git", "add", "."], check=True)
    return tmp_path


def guard():
    return importlib.import_module("vig_utils.typst_guard")


def test_entry_declarations_and_skip_globs(repo):
    assert guard().documents() == ([Path("main.typ")], [Path("templates/plain.typ")])
    (repo / ".vig-os").write_text('DEVKIT_TYPST_SKIP="main.typ,templates/**"\n')
    assert guard().documents() == ([], [])


@pytest.mark.parametrize("version,expected", [("", 1), (":0.1", 1), (":0.1.0", 0)])
def test_preview_pins(repo, version, expected):
    (repo / "main.typ").write_text(f'#import "@preview/example{version}": *\n')
    assert guard().main(["pins", "main.typ"]) == expected


def test_generated_pdf_checks_index_not_untracked_files(repo):
    pdf = repo / "generated/output.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")
    assert guard().main(["pdf"]) == 0
    subprocess.run(["git", "add", str(pdf)], check=True)
    assert guard().main(["pdf"]) == 1


@pytest.mark.parametrize(
    "diagnostic,code", [("", 0), ("warning: test", 1), ("error: test", 1)]
)
def test_compile_diagnostics_and_template_smoke(repo, monkeypatch, diagnostic, code):
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(
            argv, int(diagnostic.startswith("error:")), "", diagnostic
        )

    monkeypatch.setattr(guard().subprocess, "run", run)
    assert guard().main(["compile"]) == code
    assert len(calls) == 2
    for argv, kwargs in calls:
        assert "--ignore-system-fonts" in argv
        assert argv[argv.index("--root") + 1] == "."
        assert "--jobs" in argv
        assert argv[-1] == "/dev/null"
        assert kwargs["env"]["TZ"] == "UTC"
        assert kwargs["env"]["SOURCE_DATE_EPOCH"] == "0"
        assert "TYPST_FONT_PATHS" not in kwargs["env"]


@pytest.mark.parametrize("code", [1, 0])
def test_format_passes_tool_failure_through(repo, monkeypatch, code):
    def run(argv, **kwargs):
        assert argv == ["typstyle", "--check", "main.typ"]
        return subprocess.CompletedProcess(argv, code)

    monkeypatch.setattr(guard().subprocess, "run", run)
    assert guard().main(["format", "main.typ"]) == code
