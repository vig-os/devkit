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
        f'DEVKIT_MODULES="{"docs" if enabled else ""}"\nDEVKIT_TYPST_SKIP="drafts/**"\n'
    )
    config = seed / ".pre-commit-config.yaml"
    original = """# consumer comment
repos:
  - repo: local
    hooks:
      - id: trailing-whitespace
        entry: echo
        language: system
        exclude: '^vendor/'  # consumer exception
"""
    config.write_text(original)
    scaffold(tmp_path, seed=seed)
    dest = tmp_path / "workspace"
    assert 'DEVKIT_TYPST_SKIP="drafts/**"' in (dest / ".vig-os").read_text()
    hooks = [
        h
        for r in yaml.safe_load((dest / config.name).read_text())["repos"]
        for h in r["hooks"]
    ]
    assert any(h["id"] == "typst-compile" for h in hooks) == enabled
    assert (dest / "justfile.docs").exists() == enabled
    assert "# consumer comment" in (dest / config.name).read_text()
    if enabled:
        assert "generated" in hooks[0]["exclude"]
        assert "vendor" in hooks[0]["exclude"]
        before = (dest / config.name).read_text()
        scaffold(tmp_path, name="workspace")
        assert (dest / config.name).read_text() == before
        (dest / ".vig-os").write_text('DEVKIT_MODULES=""\n')
        scaffold(tmp_path, name="workspace")
        assert (dest / config.name).read_text() == original
        assert not (dest / "justfile.docs").exists()
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
