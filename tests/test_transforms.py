"""Tests for scripts/transforms.py — transform classes used by sync_manifest."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

scripts_dir = Path(__file__).parent.parent / "scripts"
project_root = scripts_dir.parent
sys.path.insert(0, str(project_root))


def _load_transforms():
    spec = importlib.util.spec_from_file_location(
        "transforms", scripts_dir / "transforms.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["transforms"] = module
    spec.loader.exec_module(module)
    return module


def _load_sync_manifest():
    spec = importlib.util.spec_from_file_location(
        "sync_manifest", scripts_dir / "sync_manifest.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["sync_manifest"] = module
    spec.loader.exec_module(module)
    return module


class TestTransformsModule:
    """Test that transforms module exists and exports transform classes."""

    def test_sed_transform_applies_regex_substitution(self, tmp_path):
        """Sed transform applies regex substitution to file content."""
        transforms = _load_transforms()
        f = tmp_path / "test.txt"
        f.write_text("just test-image\nline2")

        transforms.Sed(
            pattern=r"just test-image", replace="just test", target=""
        ).apply(f)

        assert f.read_text() == "just test\nline2"

    def test_remove_lines_transform_removes_matching_lines(self, tmp_path):
        """RemoveLines transform removes lines matching pattern."""
        transforms = _load_transforms()
        f = tmp_path / "test.txt"
        f.write_text("keep\nremove me\nkeep\n")

        transforms.RemoveLines(pattern=r"remove me").apply(f)

        assert f.read_text() == "keep\nkeep\n"


class TestWorkspaceInterpreterPath:
    """The synced workspace settings must point at the workspace venv."""

    def test_synced_settings_uses_workspace_relative_venv(self, tmp_path):
        """Syncing must leave the python interpreter workspace-relative, never /opt/venv."""
        sync_manifest = _load_sync_manifest()
        sync_manifest.sync(project_root, tmp_path)

        settings = json.loads((tmp_path / ".vscode" / "settings.json").read_text())
        interpreter = settings["python.defaultInterpreterPath"]

        assert interpreter == "${workspaceFolder}/.venv/bin/python3"
        assert "/opt/venv" not in interpreter


class TestRenovateChangelogTemplateNoMirrorLeak:
    """Synced renovate-changelog workflows must not leak the upstream-only mirror (#914).

    The devcontainer repo keeps assets/workspace/.devcontainer/CHANGELOG.md in
    lockstep with the root CHANGELOG.md, but consumers of the template have no
    assets/workspace/ tree. Under ``set -euo pipefail`` the mirror copies hard-fail
    on every consumer Renovate changelog run, so they must be stripped from the
    synced template while the consumer-facing logic is preserved.
    """

    def test_build_workflow_drops_workspace_mirror(self, tmp_path):
        """build.yml must not reference assets/workspace but keep the consumer copy."""
        sync_manifest = _load_sync_manifest()
        sync_manifest.sync(project_root, tmp_path)

        build = (
            tmp_path / ".github" / "workflows" / "renovate-changelog-build.yml"
        ).read_text()

        # The upstream-only mirror tree must not leak into the consumer template.
        assert "assets/workspace" not in build
        # Consumer-facing artifact copy and metadata logic must survive.
        assert "cp CHANGELOG.md changelog-artifact/" in build
        assert "metadata.env" in build
        assert "renovate-changelog-pr" in build

    def test_commit_workflow_only_commits_consumer_changelog(self, tmp_path):
        """commit.yml FILE_PATHS must list only the consumer's own CHANGELOG.md."""
        sync_manifest = _load_sync_manifest()
        sync_manifest.sync(project_root, tmp_path)

        commit = (
            tmp_path / ".github" / "workflows" / "renovate-changelog-commit.yml"
        ).read_text()

        assert "assets/workspace" not in commit
        assert "FILE_PATHS: CHANGELOG.md\n" in commit


class TestRemovePrecommitHooks:
    """Tests for RemovePrecommitHooks transform."""

    def test_preserves_section_comment_after_removed_repo(self, tmp_path):
        """Section comment preceding a kept repo must survive removal of the prior repo."""
        transforms = _load_transforms()
        f = tmp_path / ".pre-commit-config.yaml"
        f.write_text(
            "repos:\n"
            "  # Section A\n"
            "  - repo: https://example.com/a\n"
            "    rev: abc123\n"
            "    hooks:\n"
            "      - id: remove-me\n"
            "        name: remove-me\n"
            "\n"
            "  # Section B (must survive)\n"
            "  - repo: https://example.com/b\n"
            "    rev: def456\n"
            "    hooks:\n"
            "      - id: keep-me\n"
        )

        transforms.RemovePrecommitHooks(hook_ids=["remove-me"]).apply(f)

        result = f.read_text()
        assert "# Section B (must survive)" in result
        assert "keep-me" in result
        assert "# Section A" not in result
        assert "remove-me" not in result
