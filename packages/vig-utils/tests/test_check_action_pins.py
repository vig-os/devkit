"""
Tests for vig_utils.check_action_pins.

These tests run locally (pytest); they do not require the devcontainer CLI.
"""

import sys

import pytest
from vig_utils.check_action_pins import (
    SHA_PATTERN,
    USES_PATTERN,
    check_file,
    find_workflow_files,
    main,
)


class TestSHAPattern:
    """Test SHA_PATTERN regex for 40-character SHA matching."""

    @pytest.mark.parametrize(
        ("sha", "matches"),
        [
            pytest.param(
                "abcdef0123456789abcdef0123456789abcdef01", True, id="valid_40_chars"
            ),
            pytest.param(
                "abcdef0123456789abcdef0123456789abcdef0", False, id="too_short_39"
            ),
            pytest.param(
                "abcdef0123456789abcdef0123456789abcdef012", False, id="too_long_41"
            ),
            pytest.param(
                "ABCDEF0123456789ABCDEF0123456789ABCDEF01", False, id="uppercase"
            ),
            pytest.param(
                "gggggg0123456789abcdef0123456789abcdef01", False, id="non_hex"
            ),
        ],
    )
    def test_sha_pattern_boundaries(self, sha, matches):
        assert bool(SHA_PATTERN.match(sha)) == matches


class TestUSESPattern:
    """Test USES_PATTERN regex for capturing action references."""

    @pytest.mark.parametrize(
        ("line", "expected"),
        [
            pytest.param(
                "    uses: actions/checkout@v4", "actions/checkout@v4", id="simple"
            ),
            pytest.param(
                "    uses: actions/checkout@5a4ac9002d0be2fb38bd78e4b4dbde5606d7042f",
                "actions/checkout@5a4ac9002d0be2fb38bd78e4b4dbde5606d7042f",
                id="with_sha",
            ),
            pytest.param(
                "    uses: owner/repo/path@v1", "owner/repo/path@v1", id="composite"
            ),
            pytest.param(
                "    uses: ./.github/actions/my-action",
                "./.github/actions/my-action",
                id="local_action",
            ),
            pytest.param("    name: Checkout code", None, id="no_uses_prefix"),
            pytest.param(
                "    uses: actions/checkout@v4  # v4.1.1",
                "actions/checkout@v4",
                id="inline_comment_stops_at_space",
            ),
        ],
    )
    def test_uses_pattern_captures(self, line, expected):
        match = USES_PATTERN.match(line)
        if expected is None:
            assert not match
        else:
            assert match
            assert match.group(1) == expected


class TestCheckFile:
    """Test check_file() function for detecting unpinned actions."""

    def test_check_file_all_sha_pinned(self, tmp_path):
        """Test file with all actions properly SHA-pinned."""
        workflow_file = tmp_path / "workflow.yml"
        workflow_file.write_text(
            "name: CI\n"
            "on: push\n"
            "jobs:\n"
            "  test:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - uses: actions/checkout@5a4ac9002d0be2fb38bd78e4b4dbde5606d7042f\n"
            "      - uses: actions/setup-python@0a5c61591373683505ea898e09a3ea4f39ef2b9c\n"
        )
        errors = check_file(workflow_file)
        assert errors == []

    def test_check_file_unpinned_tag(self, tmp_path):
        """Test file with action pinned to tag (unpinned)."""
        workflow_file = tmp_path / "workflow.yml"
        workflow_file.write_text(
            "name: CI\n"
            "on: push\n"
            "jobs:\n"
            "  test:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - name: Checkout\n"
            "        uses: actions/checkout@v4\n"
        )
        errors = check_file(workflow_file)
        assert len(errors) == 1
        assert "unpinned action" in errors[0]
        assert "actions/checkout@v4" in errors[0]
        assert "expected 40-char SHA" in errors[0]

    def test_check_file_unpinned_branch(self, tmp_path):
        """Test file with action pinned to branch (unpinned)."""
        workflow_file = tmp_path / "workflow.yml"
        workflow_file.write_text(
            "name: CI\n"
            "on: push\n"
            "jobs:\n"
            "  test:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - name: Checkout\n"
            "        uses: actions/checkout@main\n"
        )
        errors = check_file(workflow_file)
        assert len(errors) == 1
        assert "unpinned action" in errors[0]
        assert "main" in errors[0]

    def test_check_file_missing_ref(self, tmp_path):
        """Test file with action missing @ref entirely."""
        workflow_file = tmp_path / "workflow.yml"
        workflow_file.write_text(
            "name: CI\n"
            "on: push\n"
            "jobs:\n"
            "  test:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - name: Checkout\n"
            "        uses: actions/checkout\n"
        )
        errors = check_file(workflow_file)
        assert len(errors) == 1
        assert "missing version reference" in errors[0]

    def test_check_file_local_action_skipped(self, tmp_path):
        """Test that local actions are skipped."""
        workflow_file = tmp_path / "workflow.yml"
        workflow_file.write_text(
            "name: CI\n"
            "on: push\n"
            "jobs:\n"
            "  test:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - name: Build\n"
            "        uses: ./.github/actions/my-action\n"
        )
        errors = check_file(workflow_file)
        assert errors == []

    def test_check_file_mixed_pinned_and_unpinned(self, tmp_path):
        """Test file with both pinned and unpinned actions."""
        workflow_file = tmp_path / "workflow.yml"
        workflow_file.write_text(
            "name: CI\n"
            "on: push\n"
            "jobs:\n"
            "  test:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - name: Checkout\n"
            "        uses: actions/checkout@5a4ac9002d0be2fb38bd78e4b4dbde5606d7042f\n"
            "      - name: Setup Python\n"
            "        uses: actions/setup-python@v4\n"
            "      - name: Build\n"
            "        uses: ./.github/actions/build\n"
        )
        errors = check_file(workflow_file)
        assert len(errors) == 1
        assert "unpinned action" in errors[0]
        assert "setup-python@v4" in errors[0]

    def test_check_file_multiple_unpinned(self, tmp_path):
        """Test file with multiple unpinned actions."""
        workflow_file = tmp_path / "workflow.yml"
        workflow_file.write_text(
            "name: CI\n"
            "on: push\n"
            "jobs:\n"
            "  test:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - name: Checkout\n"
            "        uses: actions/checkout@v4\n"
            "      - name: Setup Python\n"
            "        uses: actions/setup-python@v4\n"
            "      - name: Login\n"
            "        uses: docker/login-action@v2\n"
        )
        errors = check_file(workflow_file)
        assert len(errors) == 3
        assert all("unpinned action" in e for e in errors)

    def test_check_file_verbose_mode(self, tmp_path, capsys):
        """Test verbose mode prints OK status for pinned actions."""
        workflow_file = tmp_path / "workflow.yml"
        workflow_file.write_text(
            "jobs:\n"
            "  test:\n"
            "    steps:\n"
            "      - name: Checkout\n"
            "        uses: actions/checkout@5a4ac9002d0be2fb38bd78e4b4dbde5606d7042f\n"
        )
        check_file(workflow_file, verbose=True)
        captured = capsys.readouterr()
        assert "OK" in captured.out
        assert "5a4ac900" in captured.out  # First 8 chars of SHA

    def test_check_file_verbose_mode_skip_local(self, tmp_path, capsys):
        """Test verbose mode shows SKIP for local actions."""
        workflow_file = tmp_path / "workflow.yml"
        workflow_file.write_text(
            "jobs:\n"
            "  test:\n"
            "    steps:\n"
            "      - name: Build\n"
            "        uses: ./.github/actions/build\n"
        )
        check_file(workflow_file, verbose=True)
        captured = capsys.readouterr()
        assert "SKIP (local)" in captured.out

    def test_check_file_composite_action_with_sha(self, tmp_path):
        """Test composite action pinned with SHA."""
        action_file = tmp_path / "action.yml"
        action_file.write_text(
            "name: Build\n"
            "runs:\n"
            "  using: composite\n"
            "  steps:\n"
            "    - name: Build\n"
            "      uses: docker/build-push-action@b4b3e37f2c32e8e3a93f41c87e04c1d7e37f7082\n"
        )
        errors = check_file(action_file)
        assert errors == []

    def test_check_file_whitespace_variation(self, tmp_path):
        """Test uses directive with various whitespace."""
        workflow_file = tmp_path / "workflow.yml"
        workflow_file.write_text(
            "steps:\n"
            "  - name: Test\n"
            "    uses:   actions/checkout@5a4ac9002d0be2fb38bd78e4b4dbde5606d7042f\n"
            "  - name: Test2\n"
            "    uses: actions/setup-node@v4\n"
        )
        errors = check_file(workflow_file)
        assert len(errors) == 1
        assert "setup-node@v4" in errors[0]


class TestFindWorkflowFiles:
    """Test find_workflow_files() function."""

    def test_find_workflow_files_empty_repo(self, tmp_path):
        """Test finding files in empty repo returns empty list."""
        files = find_workflow_files(tmp_path)
        assert files == []

    def test_find_workflow_files_finds_workflows(self, tmp_path):
        """Test finding workflow .yml files."""
        workflows_dir = tmp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "ci.yml").touch()
        (workflows_dir / "release.yaml").touch()

        files = find_workflow_files(tmp_path)
        assert len(files) == 2
        assert any(f.name == "ci.yml" for f in files)
        assert any(f.name == "release.yaml" for f in files)

    def test_find_workflow_files_finds_composite_actions(self, tmp_path):
        """Test finding composite action files."""
        actions_dir = tmp_path / ".github" / "actions"
        build_dir = actions_dir / "build"
        build_dir.mkdir(parents=True)
        (build_dir / "action.yml").touch()

        files = find_workflow_files(tmp_path)
        assert len(files) == 1
        assert "action.yml" in files[0].name

    def test_find_workflow_files_mixed(self, tmp_path):
        """Test finding both workflows and composite actions."""
        workflows_dir = tmp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "ci.yml").touch()

        actions_dir = tmp_path / ".github" / "actions"
        build_dir = actions_dir / "build"
        build_dir.mkdir(parents=True)
        (build_dir / "action.yml").touch()

        test_dir = actions_dir / "test"
        test_dir.mkdir(parents=True)
        (test_dir / "action.yaml").touch()

        files = find_workflow_files(tmp_path)
        assert len(files) == 3

    def test_find_workflow_files_sorted(self, tmp_path):
        """Test that files are returned sorted."""
        workflows_dir = tmp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "z.yml").touch()
        (workflows_dir / "a.yml").touch()
        (workflows_dir / "m.yml").touch()

        files = find_workflow_files(tmp_path)
        names = [f.name for f in files]
        assert names == ["a.yml", "m.yml", "z.yml"]

    def test_find_workflow_files_ignores_other_dirs(self, tmp_path):
        """Test that files outside .github are ignored."""
        workflows_dir = tmp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "ci.yml").touch()

        # Create a workflows file outside .github (should be ignored)
        other_dir = tmp_path / "workflows"
        other_dir.mkdir(parents=True)
        (other_dir / "ci.yml").touch()

        files = find_workflow_files(tmp_path)
        assert len(files) == 1
        assert files[0].parent.name == "workflows"
        assert files[0].parent.parent.name == ".github"


class TestMainFunction:
    """Test main() entry point."""

    def test_main_valid_repo_all_pinned(self, tmp_path, capsys, monkeypatch):
        """Test main with all actions properly pinned."""
        workflows_dir = tmp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        workflow_file = workflows_dir / "ci.yml"
        workflow_file.write_text(
            "on: push\n"
            "jobs:\n"
            "  test:\n"
            "    steps:\n"
            "      - name: Checkout\n"
            "        uses: actions/checkout@5a4ac9002d0be2fb38bd78e4b4dbde5606d7042f\n"
        )

        monkeypatch.setattr(
            sys, "argv", ["check_action_pins.py", "--repo-root", str(tmp_path)]
        )
        exit_code = main()
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "All external actions are SHA-pinned" in captured.out

    def test_main_unpinned_actions_found(self, tmp_path, capsys, monkeypatch):
        """Test main returns error code and aggregates counts across files."""
        workflows_dir = tmp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)

        workflow1 = workflows_dir / "ci.yml"
        workflow1.write_text(
            "on: push\n"
            "jobs:\n"
            "  test:\n"
            "    steps:\n"
            "      - name: Checkout\n"
            "        uses: actions/checkout@v4\n"
            "      - name: Setup Python\n"
            "        uses: actions/setup-python@v4\n"
        )

        workflow2 = workflows_dir / "release.yml"
        workflow2.write_text(
            "on: release\n"
            "jobs:\n"
            "  publish:\n"
            "    steps:\n"
            "      - name: Upload\n"
            "        uses: actions/upload-artifact@v3\n"
        )

        monkeypatch.setattr(
            sys, "argv", ["check_action_pins.py", "--repo-root", str(tmp_path)]
        )
        exit_code = main()
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Found 3 unpinned action(s)" in captured.out
        assert "actions/checkout@v4" in captured.out

    def test_main_no_workflows_found(self, tmp_path, capsys, monkeypatch):
        """Test main when no workflow files exist."""
        monkeypatch.setattr(
            sys, "argv", ["check_action_pins.py", "--repo-root", str(tmp_path)]
        )
        exit_code = main()
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "No workflow files found" in captured.out

    def test_main_verbose_mode(self, tmp_path, capsys, monkeypatch):
        """Test main verbose mode."""
        workflows_dir = tmp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        workflow_file = workflows_dir / "ci.yml"
        workflow_file.write_text(
            "on: push\n"
            "jobs:\n"
            "  test:\n"
            "    steps:\n"
            "      - name: Checkout\n"
            "        uses: actions/checkout@5a4ac9002d0be2fb38bd78e4b4dbde5606d7042f\n"
        )

        monkeypatch.setattr(
            sys,
            "argv",
            ["check_action_pins.py", "--repo-root", str(tmp_path), "--verbose"],
        )
        exit_code = main()
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Checking" in captured.out
        assert "OK" in captured.out

    def test_main_relative_paths_in_errors(self, tmp_path, capsys, monkeypatch):
        """Test that errors show relative paths, not absolute."""
        workflows_dir = tmp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        workflow_file = workflows_dir / "ci.yml"
        workflow_file.write_text(
            "on: push\n"
            "jobs:\n"
            "  test:\n"
            "    steps:\n"
            "      - name: Checkout\n"
            "        uses: actions/checkout@v4\n"
        )

        monkeypatch.setattr(
            sys, "argv", ["check_action_pins.py", "--repo-root", str(tmp_path)]
        )
        exit_code = main()
        assert exit_code == 1
        captured = capsys.readouterr()
        # Should show relative path
        assert ".github/workflows/ci.yml" in captured.out
        # Should not show absolute path
        assert str(tmp_path) not in captured.out


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_sha_with_leading_zeros(self, tmp_path):
        """Test SHA starting with zeros."""
        workflow_file = tmp_path / "workflow.yml"
        workflow_file.write_text(
            "jobs:\n"
            "  test:\n"
            "    steps:\n"
            "      - name: Checkout\n"
            "        uses: actions/checkout@0000000000000000000000000000000000000000\n"
        )
        errors = check_file(workflow_file)
        assert errors == []

    def test_multiple_uses_on_one_line_only_first_captured(self, tmp_path):
        """Only the first uses ref on a line is captured (YAML won't have two)."""
        workflow_file = tmp_path / "workflow.yml"
        workflow_file.write_text(
            "jobs:\n"
            "  test:\n"
            "    steps:\n"
            "      - name: Test\n"
            "        uses: actions/checkout@v4 uses: actions/setup-python@v4\n"
        )
        errors = check_file(workflow_file)
        assert len(errors) == 1
        assert "actions/checkout@v4" in errors[0]
        assert "setup-python" not in errors[0]

    def test_empty_file(self, tmp_path):
        """Test checking an empty file."""
        workflow_file = tmp_path / "workflow.yml"
        workflow_file.write_text("")
        errors = check_file(workflow_file)
        assert errors == []

    def test_file_only_comments(self, tmp_path):
        """Test file with only comments."""
        workflow_file = tmp_path / "workflow.yml"
        workflow_file.write_text(
            "# This is a comment\n# uses: actions/checkout@v4\n# Another comment\n"
        )
        errors = check_file(workflow_file)
        assert errors == []

    def test_non_utf8_file(self, tmp_path):
        """Test that a file with non-UTF-8 bytes raises an error or is handled."""
        workflow_file = tmp_path / "workflow.yml"
        # Write raw bytes including invalid UTF-8 sequence
        workflow_file.write_bytes(
            b"jobs:\n"
            b"  test:\n"
            b"    steps:\n"
            b"      - name: Checkout \xff\xfe\n"
            b"        uses: actions/checkout@v4\n"
        )
        # Should raise UnicodeDecodeError since we now use encoding="utf-8"
        with pytest.raises(UnicodeDecodeError):
            check_file(workflow_file)
