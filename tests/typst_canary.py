"""Run real Typst hooks and recipes in a document fixture (Nix check #1994)."""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

config, recipes, assets, font_root = (Path(p).resolve() for p in sys.argv[1:])


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


with tempfile.TemporaryDirectory() as directory:
    os.chdir(directory)
    run("git", "init", "-q")
    run("git", "config", "user.email", "author@example.com")
    run("git", "config", "user.name", "Example Author")
    Path("guards.json").write_text(config.read_text())
    consumer = Path(".pre-commit-config.yaml")
    consumer.write_text(
        "repos:\n  - repo: local\n    hooks:\n      - id: canary\n        name: canary\n        entry: 'true'\n        language: system\n        files: '^$'\n"
    )
    Path(".gitignore").write_text("generated/\n")
    for folder in ("parts", "templates", "generated"):
        Path(folder).mkdir()
    source = '// devkit: entry\n#include "parts/body.typ"\n#sys.inputs.at("rev", default: "canonical")\n'
    Path("main.typ").write_text(source)
    Path("parts/body.typ").write_text("Hello\n")
    Path("templates/plain.typ").write_text("Template\n")
    Path("library.typ").write_text('#panic("not an entry")\n')
    Path("generated/cache.typ").write_text('#panic("ignored")\n')
    run("git", "add", ".")
    run("git", "commit", "-qm", "Fixture")

    def hook(name, expected=0):
        result = subprocess.run(
            ["prek", "run", "--config", "guards.json", name, "--all-files"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == expected, result.stdout + result.stderr

    for name in (
        "typstyle-check",
        "typst-compile",
        "typst-preview-pins",
        "forbid-generated-pdf",
    ):
        hook(name)
    for name, bad in [
        ("typstyle-check", "#let x=(1,2)\n"),
        ("typst-compile", "// devkit: entry\n#unknown()\n"),
        (
            "typst-compile",
            '// devkit: entry\n#set text(font: "Missing Example Font")\n',
        ),
        ("typst-preview-pins", '#import "@preview/example": *\n'),
        ("typst-preview-pins", '#import "@preview/example:0.1": *\n'),
        ("typst-preview-pins", '#import "@preview/example:0x1x0": *\n'),
        ("typst-preview-pins", '#import "@preview/example:0.1.0junk": *\n'),
    ]:
        Path("main.typ").write_text(bad)
        hook(name, 1)
        Path("main.typ").write_text(source)
        hook(name)
    Path("main.typ").write_text('#import "@preview/example:0.1.0": *\n')
    hook("typst-preview-pins")
    Path("main.typ").write_text(source)
    Path("outside.PDF").write_bytes(b"%PDF\n")
    run("git", "add", "outside.PDF")
    hook("forbid-generated-pdf")
    Path("generated/output.PDF").write_bytes(b"%PDF-1.7\n")
    run("git", "add", "-f", "generated/output.PDF")
    hook("forbid-generated-pdf", 1)
    run("git", "rm", "-f", "generated/output.PDF")
    hook("forbid-generated-pdf")

    def recipe(name, *args):
        return run(
            "just",
            "--justfile",
            str(recipes),
            "--working-directory",
            directory,
            name,
            *args,
        )

    # Execute the installer's actual module gate, including a real OFF run.
    script = (assets / "init-workspace.sh").read_text()
    gate = re.search(r"(?ms)^render_docs_module\(\) \{\n.*?^\}\n", script)[0]
    for enabled in (False, True, False):
        subprocess.run(
            ["bash", "-c", gate + "\nrender_docs_module"],
            check=True,
            env=dict(
                os.environ,
                WORKSPACE_DIR=directory,
                TEMPLATE_DIR=str(assets / "workspace"),
                MANIFEST_MODULES="docs" if enabled else "",
            ),
        )
        assert ("typst-compile" in consumer.read_text()) == enabled
        Path("main.typ").write_text("#let x=(1,2)\n")
        result = subprocess.run(
            ["prek", "run", "--all-files"], capture_output=True, text=True
        )
        assert result.returncode == int(enabled), result.stdout + result.stderr
    Path("main.typ").write_text(source)

    # Prove the fixture is a discovered system font, rather than an unknown font.
    assert "Liberation Sans" in run("typst", "fonts")
    assert "Liberation Sans" not in run("typst", "fonts", "--ignore-system-fonts")
    os.environ["TYPST_FONT_PATHS"] = str(font_root)
    branded = '//devkit: entry  \n#set text(font: "Liberation Sans")\nBrand\n'
    Path("main.typ").write_text(branded)
    hook("typst-compile", 1)
    Path("fonts").mkdir()
    shutil.copy(next(font_root.rglob("LiberationSans-Regular.ttf")), "fonts/brand.ttf")
    Path(".vig-os").write_text('DEVKIT_TYPST_FONT_PATHS="fonts"\n')
    hook("typst-compile")
    for name in ("typst", "typst-canonical"):
        recipe(name)
        assert "LiberationSans" in run("pdffonts", "generated/main.pdf")
    digest = hashlib.sha256(Path("generated/main.pdf").read_bytes()).digest()
    os.environ.update(SOURCE_DATE_EPOCH="987654321", TZ="Pacific/Honolulu")
    recipe("typst-canonical")
    assert hashlib.sha256(Path("generated/main.pdf").read_bytes()).digest() == digest
    Path("main.typ").write_text(
        branded + '#set text(font: "Liberation Serif")\nSystem\n'
    )
    hook("typst-compile", 1)
    Path("main.typ").write_text(source)
    Path(".vig-os").unlink()
    run("git", "add", ".")
    run("git", "commit", "-qm", "Complete fixtures")

    recipe("typst", "--deps")
    stamp = run("git", "rev-parse", "--short=8", "HEAD").strip()
    assert stamp in run("pdftotext", "generated/main.pdf", "-")
    assert "parts/body.typ" in Path("generated/main.deps.json").read_text()
    assert not Path("generated/library.pdf").exists()
    assert not Path("templates/generated").exists()
    Path("main.typ").write_text(source + "Dirty\n")
    recipe("typst")
    assert stamp + "-dirty" in run("pdftotext", "generated/main.pdf", "-")
    recipe("typst-canonical")
    digest = hashlib.sha256(Path("generated/main.pdf").read_bytes()).digest()
    os.environ.update(
        SOURCE_DATE_EPOCH="123456789",
        TZ="Pacific/Honolulu",
        TYPST_FONT_PATHS=str(font_root),
    )
    recipe("typst-canonical", "--deps")
    assert hashlib.sha256(Path("generated/main.pdf").read_bytes()).digest() == digest
    assert "canonical" in run("pdftotext", "generated/main.pdf", "-")
    probe = json.loads(recipe("typst-probe"))
    assert set(probe) == {"typst", "typstyle", "tinymist"}
    for tool, identity in probe.items():
        assert identity["path"] == str(Path(shutil.which(tool)).resolve())
        assert re.fullmatch(r"\d+\.\d+\.\d+", identity["version"]), identity
    reported = probe["tinymist"]
    assert (
        reported["version"]
        == re.search(r"-tinymist-(\d+\.\d+\.\d+)/", reported["path"])[1]
    )
    Path(".vig-os").write_text('DEVKIT_TYPST_SKIP="main.typ,templates/**"\n')
    Path("main.typ").write_text("// devkit: entry\n#unknown()\n")
    hook("typst-compile")
print("Typst hook and recipe canaries passed")
