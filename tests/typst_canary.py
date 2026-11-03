"""Run real Typst hooks and recipes in a document fixture (Nix check #1994)."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

config, recipes = (Path(p).resolve() for p in sys.argv[1:])


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


with tempfile.TemporaryDirectory() as directory:
    os.chdir(directory)
    run("git", "init", "-q")
    run("git", "config", "user.email", "author@example.com")
    run("git", "config", "user.name", "Example Author")
    Path("guards.json").write_text(config.read_text())
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
    ]:
        Path("main.typ").write_text(bad)
        hook(name, 1)
        Path("main.typ").write_text(source)
        hook(name)
    Path("main.typ").write_text('#import "@preview/example:0.1.0": *\n')
    hook("typst-preview-pins")
    Path("main.typ").write_text(source)
    Path("generated/output.pdf").write_bytes(b"%PDF-1.7\n")
    run("git", "add", "-f", "generated/output.pdf")
    hook("forbid-generated-pdf", 1)
    run("git", "rm", "-f", "generated/output.pdf")
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
        TYPST_FONT_PATHS="/missing",
    )
    recipe("typst-canonical", "--deps")
    assert hashlib.sha256(Path("generated/main.pdf").read_bytes()).digest() == digest
    assert "canonical" in run("pdftotext", "generated/main.pdf", "-")
    assert set(json.loads(recipe("typst-probe"))) == {"typst", "typstyle", "tinymist"}
    Path(".vig-os").write_text('DEVKIT_TYPST_SKIP="main.typ,templates/**"\n')
    Path("main.typ").write_text("// devkit: entry\n#unknown()\n")
    hook("typst-compile")
print("Typst hook and recipe canaries passed")
