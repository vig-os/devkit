"""Tests for scripts/transforms.py — transform classes used by sync_manifest."""

from __future__ import annotations

import sys
from pathlib import Path

scripts_dir = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir.parent))


def _load_transforms():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "transforms", scripts_dir / "transforms.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["transforms"] = module
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


class TestReplacePrecommitRepoBlock:
    """Tests for ReplacePrecommitRepoBlock transform (#697 scaffold decoupling)."""

    def test_replaces_local_block_and_preserves_next_section(self, tmp_path):
        """A repo-local `language: system` block is swapped for an upstream block.

        The scaffolded config must keep self-contained (pre-commit-managed) hooks
        so a downstream workspace's pre-commit runs without the flake toolchain on
        PATH, while the repo itself keeps `language: system`. The following section
        (and the rest of the file) must be preserved intact.
        """
        transforms = _load_transforms()
        f = tmp_path / ".pre-commit-config.yaml"
        f.write_text(
            "repos:\n"
            "  # Python Linting and Formatting (Ruff, sourced from the flake)\n"
            "  - repo: local\n"
            "    hooks:\n"
            "      - id: ruff\n"
            "        entry: ruff check --fix\n"
            "        language: system\n"
            "        types: [python]\n"
            "      - id: ruff-format\n"
            "        entry: ruff format\n"
            "        language: system\n"
            "        types: [python]\n"
            "\n"
            "  # YAML Linting\n"
            "  - repo: https://example.com/yaml\n"
            "    rev: x\n"
            "    hooks:\n"
            "      - id: yamllint\n"
        )

        transforms.ReplacePrecommitRepoBlock(
            hook_id="ruff",
            replacement=(
                "  # Python Linting and Formatting (Ruff)\n"
                "  - repo: https://github.com/astral-sh/ruff-pre-commit\n"
                "    rev: deadbeef  # v0.14.3\n"
                "    hooks:\n"
                "      - id: ruff\n"
                "        args: [--fix]\n"
                "      - id: ruff-format\n"
                "\n"
            ),
        ).apply(f)

        result = f.read_text()
        # local language:system block is gone
        assert "repo: local" not in result
        assert "language: system" not in result
        # upstream block restored (both ruff and ruff-format)
        assert "astral-sh/ruff-pre-commit" in result
        assert "args: [--fix]" in result
        assert "id: ruff-format" in result
        # the following section is preserved intact
        assert "# YAML Linting" in result
        assert "id: yamllint" in result

    def test_noop_when_hook_absent(self, tmp_path):
        """Absent hook id leaves the file unchanged."""
        transforms = _load_transforms()
        f = tmp_path / ".pre-commit-config.yaml"
        original = "repos:\n  - repo: local\n    hooks:\n      - id: other\n"
        f.write_text(original)

        transforms.ReplacePrecommitRepoBlock(hook_id="ruff", replacement="X\n").apply(f)

        assert f.read_text() == original
