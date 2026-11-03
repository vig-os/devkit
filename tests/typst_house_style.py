"""Real-tool contract for the offline house style (also a sandboxed Nix check)."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

package_path, recipes, hooks, version = sys.argv[1:]
package_path = Path(package_path).resolve()
recipes, hooks = Path(recipes).resolve(), Path(hooks).resolve()
manifest = package_path / "local/devkit-docs" / version / "typst.toml"
assert tomllib.loads(manifest.read_text())["package"]["version"] == version
os.environ.update(
    TYPST_PACKAGE_PATH=str(package_path),
    SOURCE_DATE_EPOCH="0",
    TZ="UTC",
)


def run(*args):
    result = subprocess.run(args, check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "warning:" not in result.stderr, result.stderr
    return result.stdout


with tempfile.TemporaryDirectory() as directory:
    os.chdir(directory)
    # Empty cache and HOME make accidental network/cache dependencies observable
    # in the Nix sandbox, which has no network.
    Path("home").mkdir()
    os.environ.update(
        HOME=str(Path("home").resolve()),
        TYPST_PACKAGE_CACHE_PATH=str(Path("cache").resolve()),
    )
    run("git", "init", "-q")
    run("git", "config", "user.email", "author@example.com")
    run("git", "config", "user.name", "Example Author")
    Path(".gitignore").write_text("generated/\nhome/\ncache/\n")
    Path("guards.json").write_text(hooks.read_text())
    prefix = f'#import "@local/devkit-docs:{version}": *\n'
    source = (
        prefix
        + """#show: document.with(
  title: "House Style Contract",
  subtitle: "A neutral document",
  authors: ("Example Author",),
  date: "2026-11-03",
  version: "2.0",
  status: "Draft",
  doc-id: "EX-001",
)
#context {
  assert.eq(page.width, 210mm)
  assert.eq(page.height, 297mm)
  assert.eq(page.margin, 2.5cm)
  assert.eq(text.size, 11pt)
}
= Introduction
#note[Note body]
#warning[Warning body]
#doc-ref("EX-002", title: "Related document")
#revision-history((version: "1.0", date: "2026-11-01", description: "Initial issue"))
#fig(rect(width: 20mm, height: 10mm), caption: [Rectangle caption])
#fig(table(columns: 2, table.header([Name], [Value]), [Alpha], number(12.3)), caption: [Table caption])
#pagebreak()
= Continuation
#table(columns: 2, table.header([Repeated header], [Value]), ..range(100).map(n => ([Row #n], number(n))).flatten())
#pagebreak()
#cetz.canvas({ cetz.draw.line((0, 0), (1, 1)) })
#fletcher.diagram(fletcher.node((0, 0), [Offline diagram]))
"""
    )
    Path("main.typ").write_text("// devkit: entry\n" + source)
    run("typstyle", "-i", "main.typ")
    run("git", "add", ".")
    run("git", "commit", "-qm", "Fixture")
    for guard in ("typstyle-check", "typst-compile", "typst-preview-pins"):
        run("prek", "run", "--config", "guards.json", guard, "--all-files")

    def recipe(name):
        run("just", "--justfile", str(recipes), "--working-directory", directory, name)

    recipe("typst")
    stamp = run("git", "rev-parse", "--short=8", "HEAD").strip()
    text = run("pdftotext", "-layout", "generated/main.pdf", "-")
    pages = text.rstrip("\f\n").split("\f")
    for index, page in enumerate(pages, 1):
        assert "House Style Contract" in page
        assert stamp in page
        assert f"{index} / {len(pages)}" in page
    for value in (
        "A neutral document",
        "Example Author",
        "2026-11-03",
        "2.0",
        "Draft",
        "EX-001",
        "Note body",
        "Warning body",
        "EX-002",
        "Initial issue",
        "Rectangle caption",
        "Offline diagram",
    ):
        assert value in text, value
    assert text.index("Table caption") < text.index("Alpha")
    assert text.count("Repeated header") >= 2
    assert "LibertinusSerif-Bold" in run("pdffonts", "generated/main.pdf")
    figures = json.loads(
        run("typst", "query", "--ignore-system-fonts", "main.typ", "figure")
    )
    assert figures[0]["caption"]["position"] == "bottom"
    assert figures[1]["caption"]["position"] == "top"
    # A single plain table, exported as SVG: exactly three horizontal rules,
    # no vertical borders. This proves the default show rule reaches table().
    Path("rules.typ").write_text(
        prefix
        + "#show: document.with()\n#table(columns: 2, table.header([A], [B]), [C], [D])\n"
    )
    run(
        "typst",
        "compile",
        "--ignore-system-fonts",
        "--format",
        "svg",
        "rules.typ",
        "rules.svg",
    )
    root = ET.parse("rules.svg").getroot()
    paths = [
        p.attrib.get("d", "")
        for p in root.iter()
        if p.tag.endswith("path") and p.attrib.get("stroke") not in (None, "none")
    ]
    assert len(paths) == 3, paths
    assert all(
        "L" in p and p.split("L")[0].split()[-1] == p.split("L")[1].split()[-1]
        for p in paths
    ), paths
    Path("rules.typ").unlink()
    Path("rules.svg").unlink()
    recipe("typst-canonical")
    digest = hashlib.sha256(Path("generated/main.pdf").read_bytes()).digest()
    assert stamp not in run("pdftotext", "generated/main.pdf", "-")
    os.environ.update(SOURCE_DATE_EPOCH="123456789", TZ="Pacific/Honolulu")
    recipe("typst-canonical")
    assert hashlib.sha256(Path("generated/main.pdf").read_bytes()).digest() == digest
    for argument in ("", ", caption: none"):
        Path("main.typ").write_text(
            prefix + "#show: document.with()\n#fig(rect()" + argument + ")\n"
        )
        result = subprocess.run(
            ["typst-guard", "compile"], check=False, capture_output=True, text=True
        )
        assert result.returncode == 1
        assert "caption" in result.stderr
    # All metadata is optional, including the title block.
    Path("main.typ").write_text(prefix + "#show: document.with()\nOptional metadata\n")
    run("typst-guard", "compile")
print("House-style contracts passed")
