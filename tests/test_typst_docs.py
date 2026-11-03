"""Opt-in Typst scaffold reconciliation and recipe wiring (#1994)."""

import json
import os
import subprocess

import pytest
import yaml

from tests.workflow_scaffold import REPO_ROOT, scaffold


@pytest.mark.parametrize("enabled", [False, True])
def test_scaffold_docs_activation_and_reconciliation(tmp_path, enabled):
    seed = tmp_path / "seed"
    seed.mkdir()
    manifest = seed / ".vig-os"
    manifest.write_text(
        f'DEVKIT_MODULES="{"docs" if enabled else ""}"\nDEVKIT_GLOSSARY="terms.yaml"\nDEVKIT_GLOSSARY_SOURCES="docs/**"\nDEVKIT_TYPST_SKIP="drafts/**"\nDEVKIT_TYPST_FONT_PATHS="fonts:branding"\n'
    )
    config = seed / ".pre-commit-config.yaml"
    original = """# consumer comment
repos:
  - repo: local
    hooks:
      - id: trailing-whitespace
        name: existing
        entry: echo
        language: system
        exclude: '^vendor/'  # consumer exception
"""
    config.write_text(original)
    scaffold(tmp_path, seed=seed)
    dest = tmp_path / "workspace"
    assert 'DEVKIT_TYPST_SKIP="drafts/**"' in (dest / ".vig-os").read_text()
    assert 'DEVKIT_TYPST_FONT_PATHS="fonts:branding"' in (dest / ".vig-os").read_text()
    hooks = [
        h
        for r in yaml.safe_load((dest / config.name).read_text())["repos"]
        for h in r["hooks"]
    ]
    for hook_id in (
        "typst-compile",
        "glossary-schema",
        "glossary-terms",
        "typst-content",
    ):
        assert any(h["id"] == hook_id for h in hooks) == enabled
    assert 'DEVKIT_GLOSSARY="terms.yaml"' in (dest / ".vig-os").read_text()
    assert 'DEVKIT_GLOSSARY_SOURCES="docs/**"' in (dest / ".vig-os").read_text()
    assert (dest / "justfile.devkit-docs").exists() == enabled
    assert "# consumer comment" in (dest / config.name).read_text()
    if enabled:
        fixer = next(hook for hook in hooks if hook["id"] == "trailing-whitespace")
        assert "generated" in fixer["exclude"]
        assert "vendor" in fixer["exclude"]
        before = (dest / config.name).read_text()
        scaffold(tmp_path, name="workspace")
        assert (dest / config.name).read_text() == before
        (dest / ".vig-os").write_text('DEVKIT_MODULES=""\n')
        scaffold(tmp_path, name="workspace")
        assert (dest / config.name).read_text() == original
        assert not (dest / "justfile.devkit-docs").exists()
    else:
        assert (dest / config.name).read_text() == original


def test_docs_recipes_forward_arguments(tmp_path):
    runner = tmp_path / "typst-guard"
    runner.write_text(
        "#!/usr/bin/env python3\nimport json, sys\nprint(json.dumps(sys.argv[1:]))\n"
    )
    runner.chmod(0o755)
    for recipe, args, expected in [
        ("typst", ["--deps"], ["build", "--deps"]),
        ("typst-canonical", [], ["canonical"]),
        ("typst-probe", [], ["probe"]),
    ]:
        result = subprocess.run(
            [
                "just",
                "--justfile",
                str(REPO_ROOT / "assets/justfile.d/docs.justfile"),
                recipe,
                *args,
            ],
            env={**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}"},
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout) == expected


@pytest.mark.parametrize("enabled", [False, True])
def test_consumer_owned_docs_justfile_survives_upgrade(tmp_path, enabled):
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / ".vig-os").write_text(f'DEVKIT_MODULES="{"docs" if enabled else ""}"\n')
    original = "# Consumer recipes\nthis is deliberately invalid just syntax\n"
    (seed / "justfile.docs").write_text(original)
    scaffold(tmp_path, seed=seed)
    assert (
        "import? 'justfile.docs'" not in (tmp_path / "workspace/justfile").read_text()
    )
    assert (tmp_path / "workspace/justfile.docs").read_text() == original
    parsed = subprocess.run(
        ["just", "--justfile", str(tmp_path / "workspace/justfile"), "--list"],
        capture_output=True,
        text=True,
    )
    assert parsed.returncode == 0, parsed.stderr
    assert (
        "mod devkit-docs 'justfile.devkit-docs'"
        in (tmp_path / "workspace/justfile").read_text()
    ) == enabled


def test_reconciliation_failure_does_not_abort_installer(tmp_path):
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / ".vig-os").write_text('DEVKIT_MODULES="docs"\n')
    original = "repos: [{repo: local, hooks: [{id: mine, name: mine, entry: echo, language: system}]}]\n"
    (seed / ".pre-commit-config.yaml").write_text(original)
    scaffold(tmp_path, seed=seed)
    assert (tmp_path / "workspace/.pre-commit-config.yaml").read_text() == original


def test_docs_preview_reports_hooks_and_recipes(tmp_path):
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / ".vig-os").write_text('DEVKIT_MODULES="docs"\n')
    result = scaffold(tmp_path, seed=seed, preview=True)
    assert "docs hooks" in result.stdout
    assert "justfile.devkit-docs" in result.stdout


@pytest.mark.parametrize("enabled", [False, True])
def test_unmanaged_reserved_recipe_file_is_not_imported(tmp_path, enabled):
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / ".vig-os").write_text(f'DEVKIT_MODULES="{"docs" if enabled else ""}"\n')
    original = "consumer syntax that just cannot parse\n"
    (seed / "justfile.devkit-docs").write_text(original)
    scaffold(tmp_path, seed=seed)
    assert (tmp_path / "workspace/justfile.devkit-docs").read_text() == original
    assert (
        "mod devkit-docs 'justfile.devkit-docs'"
        not in (tmp_path / "workspace/justfile").read_text()
    )


@pytest.mark.parametrize("recipe", ["typst", "typst-canonical", "typst-probe"])
def test_consumer_recipe_names_do_not_clash(tmp_path, recipe):
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / ".vig-os").write_text('DEVKIT_MODULES="docs"\n')
    (seed / "justfile.local").write_text(f"{recipe}:\n    @echo consumer\n")
    scaffold(tmp_path, seed=seed)
    justfile = tmp_path / "workspace/justfile"
    for args in [["--list"], [recipe], ["--show", "devkit-docs::typst"]]:
        result = subprocess.run(
            ["just", "--justfile", str(justfile), *args], capture_output=True, text=True
        )
        assert result.returncode == 0, result.stderr


def test_preview_removes_hooks_without_recipe_file(tmp_path):
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / ".vig-os").write_text('DEVKIT_MODULES="docs"\n')
    scaffold(tmp_path, seed=seed)
    dest = tmp_path / "workspace"
    (dest / "justfile.devkit-docs").unlink()
    (dest / ".vig-os").write_text('DEVKIT_MODULES=""\n')
    result = scaffold(tmp_path, preview=True)
    assert "  -  managed docs hooks" in result.stdout


def test_preview_keeps_consumer_owned_recipe_file(tmp_path):
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / ".vig-os").write_text('DEVKIT_MODULES=""\n')
    (seed / "justfile.devkit-docs").write_text("# Consumer recipes\n")
    result = scaffold(tmp_path, seed=seed, preview=True)
    assert not any(
        "  -  " in line and "justfile.devkit-docs" in line
        for line in result.stdout.splitlines()
    )
    assert "consumer-owned justfile.devkit-docs retained" in result.stdout


@pytest.mark.parametrize("filename", ["justfile", "justfile.project", "justfile.local"])
@pytest.mark.parametrize("name", ["docs", "devkit-docs"])
@pytest.mark.parametrize("kind", ["recipe", "alias", "module"])
def test_docs_namespace_collisions_across_enable_cycle(tmp_path, filename, name, kind):
    (tmp_path / "justfile").write_text(
        "import? 'justfile.project'\nimport? 'justfile.local'\n"
    )
    (tmp_path / "consumer.just").write_text("target:\n    @echo consumer\n")
    declarations = {
        "recipe": f"{name}:\n    @echo consumer\n",
        "alias": f"target:\n    @echo consumer\nalias {name} := target\n",
        "module": f"mod {name} 'consumer.just'\n",
    }
    with (tmp_path / filename).open("a") as stream:
        stream.write(declarations[kind])
    script = (REPO_ROOT / "assets/init-workspace.sh").read_text()
    functions = script.split("docs_recipes_consumer_owned()", 1)[1].split(
        "# One pass, two gates.", 1
    )[0]
    for enabled in [True, False, True]:
        result = subprocess.run(
            [
                "bash",
                "-c",
                "docs_recipes_consumer_owned()" + functions + "\nrender_docs_module",
            ],
            env={
                **os.environ,
                "WORKSPACE_DIR": str(tmp_path),
                "TEMPLATE_DIR": str(REPO_ROOT / "assets/workspace"),
                "MANIFEST_MODULES": "docs" if enabled else "",
            },
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        parsed = subprocess.run(
            ["just", "--justfile", str(tmp_path / "justfile"), "--list"],
            capture_output=True,
            text=True,
        )
        assert parsed.returncode == 0, parsed.stderr
        loaded = (
            "mod devkit-docs 'justfile.devkit-docs'"
            in (tmp_path / "justfile").read_text()
        )
        assert loaded == (enabled and name != "devkit-docs")
        if enabled and name == "devkit-docs":
            assert result.stderr.count("Notice: devkit-docs name clash") == 1
            assert "rename" in result.stderr and "rerun" in result.stderr


@pytest.mark.parametrize("anchor", [False, True])
def test_docs_off_consumer_exclude_does_not_trigger_reconciliation(tmp_path, anchor):
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / ".vig-os").write_text('DEVKIT_MODULES=""\n')
    original = (
        "repos:\n  - repo: local\n    hooks:\n      - id: trailing-whitespace\n        name: existing\n        entry: echo\n        language: system\n        exclude: "
        + ("&consumer " if anchor else "")
        + "'(^|/)generated/'\n"
    )
    (seed / ".pre-commit-config.yaml").write_text(original)
    scaffold(tmp_path, seed=seed)
    for _ in range(2):
        result = scaffold(tmp_path)
        assert "reconcile-preserved-hooks:" not in result.stderr
        assert "docs hook reconciliation" not in result.stderr
        assert (
            tmp_path / "workspace/.pre-commit-config.yaml"
        ).read_bytes() == original.encode()
