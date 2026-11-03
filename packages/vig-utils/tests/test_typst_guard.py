"""Document-repository canaries for the opt-in Typst surface (#1994)."""

import importlib
import os
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


@pytest.mark.parametrize(
    "marker", ["//devkit: entry", "// devkit: entry", "// devkit: entry  \t"]
)
def test_entry_marker_whitespace(repo, marker):
    (repo / "main.typ").write_text(marker + "\nHello\n")
    assert guard().documents()[0] == [Path("main.typ")]


def test_unmarked_entries_warn(repo, capsys):
    (repo / "unmarked.typ").write_text('#set page(paper: "a4")\n= Title\n')
    guard().documents()
    assert "unmarked.typ" in capsys.readouterr().err
    (repo / "main.typ").write_text("Hello\n")
    guard().documents()
    assert "zero entries" in capsys.readouterr().err


@pytest.mark.parametrize(
    "name,expected",
    [
        ("generated/a.PDF", 1),
        ("Generated/a.pdf", 1),
        ("docs/generated/a.PdF", 1),
        ("other/a.PDF", 0),
        ("notgenerated/a.PDF", 0),
    ],
)
def test_generated_pdf_scope_is_case_insensitive(repo, name, expected):
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF\n")
    subprocess.run(["git", "add", "-f", name], check=True)
    assert guard().main(["pdf"]) == expected


def test_project_font_paths_reach_every_compile_mode(repo, monkeypatch):
    for folder in ("fonts", "branding"):
        (repo / folder).mkdir()
    (repo / ".vig-os").write_text('DEVKIT_TYPST_FONT_PATHS="fonts:branding"\n')
    calls = []

    def run(argv, **kwargs):
        if argv[0] != "typst":
            return subprocess.CompletedProcess(
                argv, 0, "12345678" if argv[1] == "rev-parse" else "", ""
            )
        calls.append(argv)
        assert [
            argv[i + 1] for i, value in enumerate(argv) if value == "--font-path"
        ] == ["fonts", "branding"]
        assert "--ignore-system-fonts" in argv
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(guard().subprocess, "run", run)
    for mode in ("compile", "canonical", "build"):
        assert guard().main([mode]) == 0
    assert len(calls) == 6


@pytest.mark.parametrize("value", ["../outside", "/usr/share/fonts", "missing"])
def test_project_font_paths_reject_unreproducible_inputs(repo, value):
    (repo / ".vig-os").write_text(f'DEVKIT_TYPST_FONT_PATHS="{value}"\n')
    assert guard().main(["compile"]) == 1


def test_probe_parses_real_versions_and_resolves_paths(repo, monkeypatch, capsys):
    import json
    import os
    import shlex

    binary = repo / "bin"
    binary.mkdir()
    versions = {
        "typst": "typst 0.15.1 (abcdef)",
        "typstyle": "typstyle \nVersion: 0.15.2\nBuild Timestamp: today",
        "tinymist": "tinymist \nVersion: 0.15.10\nTypst Version: 0.15.1",
    }
    for tool, version in versions.items():
        target = binary / (tool + "-real")
        target.write_text("#!/bin/sh\nprintf '%s\\n' " + shlex.quote(version) + "\n")
        target.chmod(0o755)
        (binary / tool).symlink_to(target)
    monkeypatch.setenv("PATH", f"{binary}:{os.environ['PATH']}")
    assert guard().main(["probe"]) == 0
    data = json.loads(capsys.readouterr().out)
    for tool, version in [
        ("typst", "0.15.1"),
        ("typstyle", "0.15.2"),
        ("tinymist", "0.15.10"),
    ]:
        assert data[tool]["version"] == version
        assert data[tool]["path"] == str((binary / tool).resolve())


def test_parts_only_repository_warns_about_zero_entries(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "parts").mkdir()
    (tmp_path / "parts/body.typ").write_text("Hello\n")
    assert guard().documents() == ([], [])
    assert "zero entries" in capsys.readouterr().err


def test_package_paths_prefer_first_registry_and_clean_union(
    repo, monkeypatch, tmp_path
):
    roots = [tmp_path / "first", tmp_path / "second"]
    for root, names in zip(roots, [("shared",), ("shared", "consumer")], strict=True):
        for name in names:
            package = root / "local" / name / "0.1.0"
            package.mkdir(parents=True)
            (package / "marker").write_text(root.name)
    monkeypatch.setenv("TYPST_PACKAGE_PATH", os.pathsep.join(map(str, roots)))
    unions = []

    def run(argv, **kwargs):
        union = Path(kwargs["env"]["TYPST_PACKAGE_PATH"])
        unions.append(union)
        assert (union / "local/shared/0.1.0/marker").read_text() == "first"
        assert (union / "local/consumer/0.1.0/marker").read_text() == "second"
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(guard().subprocess, "run", run)
    assert guard().main(["compile"]) == 0
    assert unions and all(not union.exists() for union in unions)


def test_dependency_paths_survive_composed_registry_cleanup(
    repo, monkeypatch, tmp_path
):
    import json

    roots = [tmp_path / "first", tmp_path / "second"]
    for root in roots:
        package = root / "local/mypkg/0.1.0"
        package.mkdir(parents=True)
        (package / "lib.typ").write_text("Content")
    monkeypatch.setenv("TYPST_PACKAGE_PATH", os.pathsep.join(map(str, roots)))

    def run(argv, **kwargs):
        union = Path(kwargs["env"]["TYPST_PACKAGE_PATH"])
        if "--deps" not in argv:
            return subprocess.CompletedProcess(argv, 0, "", "")
        deps = Path(argv[argv.index("--deps") + 1])
        deps.write_text(
            json.dumps(
                {
                    "inputs": [str(union / "local/mypkg/0.1.0/lib.typ")],
                    "outputs": ["generated/main.pdf"],
                }
            )
        )
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(guard().subprocess, "run", run)
    assert guard().main(["canonical", "--deps"]) == 0
    deps = json.loads(Path("generated/main.deps.json").read_text())
    assert deps["inputs"] == [str(roots[0] / "local/mypkg/0.1.0/lib.typ")]
    assert all(Path(name).is_file() for name in deps["inputs"])


def test_compile_transports_configured_yaml_natively(repo, monkeypatch):
    (repo / ".vig-os").write_text('DEVKIT_GLOSSARY="terms.yaml"\n')
    contents = "- id: sample\n  term: Sample\n  definition: A specimen.\n  kind: term\n"
    (repo / "terms.yaml").write_text(contents)
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(guard().subprocess, "run", run)
    assert guard().main(["compile"]) == 0
    assert all("devkit-glossary=" + contents in argv for argv in calls)


def test_compile_rejects_glossary_outside_repository(repo, capsys):
    (repo / ".vig-os").write_text('DEVKIT_GLOSSARY="../outside.yaml"\n')
    assert guard().main(["compile"]) == 1
    assert "repository-relative" in capsys.readouterr().err
