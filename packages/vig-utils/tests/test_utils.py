"""
Tests for vig_utils.utils.

Covers:
- sed_inplace
- substitute_in_file
- update_version_line
- parse_args
- main
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from vig_utils import utils

sed_inplace = utils.sed_inplace
substitute_in_file = utils.substitute_in_file
update_version_line = utils.update_version_line
parse_args = utils.parse_args
find_repo_root = utils.find_repo_root
agent_blocklist_path = utils.agent_blocklist_path
load_blocklist = utils.load_blocklist
contains_agent_fingerprint = utils.contains_agent_fingerprint


class TestSubstituteInFile:
    """Test substitute_in_file (shared substitution used by sed_inplace and Sed transform)."""

    def test_literal_replacement_global(self, tmp_path):
        """Literal replacement replaces all occurrences."""
        f = tmp_path / "test.txt"
        f.write_text("foo bar foo")
        substitute_in_file(f, "foo", "bar", regex=False)
        assert f.read_text() == "bar bar bar"

    def test_regex_replacement(self, tmp_path):
        """Regex replacement uses re.sub."""
        f = tmp_path / "test.txt"
        f.write_text("just test-image")
        substitute_in_file(f, r"just test-image", "just test", regex=True)
        assert f.read_text() == "just test"


class TestSedInplace:
    """Test sed_inplace function from vig_utils.utils."""

    def test_sed_inplace_global_replacement(self, tmp_path):
        """Test global replacement (g flag)."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("foo bar foo baz foo")

        sed_inplace("s|foo|bar|g", test_file)

        assert test_file.read_text() == "bar bar bar baz bar"

    def test_sed_inplace_single_replacement(self, tmp_path):
        """Test single replacement (no g flag)."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("foo bar foo baz foo")

        sed_inplace("s|foo|bar|", test_file)

        assert test_file.read_text() == "bar bar foo baz foo"

    def test_sed_inplace_slash_delimiter(self, tmp_path):
        """Test replacement with slash delimiter."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("old value old")

        sed_inplace("s/old/new/g", test_file)

        assert test_file.read_text() == "new value new"

    def test_sed_inplace_hash_delimiter(self, tmp_path):
        """Test replacement with hash delimiter."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("comment # old # more")

        # Replace " old " with " new " (spaces included)
        sed_inplace("s# old # new #g", test_file)

        assert test_file.read_text() == "comment # new # more"

    def test_sed_inplace_unsupported_command(self, tmp_path):
        """Test that ValueError is raised for unsupported sed commands."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        with pytest.raises(ValueError, match="Unsupported sed command"):
            sed_inplace("d|pattern|", test_file)  # 'd' is delete, not supported

    def test_sed_inplace_invalid_pattern(self, tmp_path):
        """Test that ValueError is raised for invalid patterns."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        with pytest.raises(ValueError, match="Invalid sed pattern"):
            sed_inplace("s|only|", test_file)  # Missing replacement

    def test_sed_inplace_pattern_too_short(self, tmp_path):
        """Test that ValueError is raised for patterns that are too short."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        # Minimum valid pattern is 4 chars: s<delim>..., so 's|a' (3 chars) should fail
        with pytest.raises(ValueError, match="Invalid sed pattern"):
            sed_inplace("s|a", test_file)


class TestUpdateVersionLine:
    """Test update_version_line function from vig_utils.utils."""

    def test_update_version_line_success(self, tmp_path):
        """Test successful version line update."""
        readme_file = tmp_path / "README.md"
        readme_file.write_text(
            "# Test\n- **Version**: [dev](url), 2025-01-01\n- **Size**: ~100 MB\n"
        )

        result = update_version_line(
            readme_file, "0.2.0", "https://example.com/release", "2025-12-10"
        )

        expected = "- **Version**: [0.2.0](https://example.com/release), 2025-12-10"
        assert result == expected

        content = readme_file.read_text()
        assert expected in content
        assert "- **Size**: ~100 MB" in content  # Other content preserved

    def test_update_version_line_not_found(self, tmp_path):
        """Test that ValueError is raised when version line is not found."""
        readme_file = tmp_path / "README.md"
        readme_file.write_text("# Test\nNo version line here\n")

        with pytest.raises(ValueError, match="Version line not found"):
            update_version_line(
                readme_file, "0.2.0", "https://example.com/release", "2025-12-10"
            )

    def test_update_version_line_multiple_matches(self, tmp_path):
        """Test that only first version line is updated."""
        readme_file = tmp_path / "README.md"
        readme_file.write_text(
            "- **Version**: [old](url), date\n- **Version**: [old2](url), date2\n"
        )

        # Should raise error because pattern matches multiple lines
        # but subn with count=1 should only replace first
        update_version_line(
            readme_file, "0.2.0", "https://example.com/release", "2025-12-10"
        )

        content = readme_file.read_text()
        assert (
            "- **Version**: [0.2.0](https://example.com/release), 2025-12-10" in content
        )
        assert "- **Version**: [old2](url), date2" in content  # Second line unchanged


class TestParseArgs:
    """Tests for parse_args function from vig_utils.utils."""

    def test_parse_version_command(self):
        """parse_args should parse 'version' subcommand with all arguments."""
        with patch(
            "sys.argv",
            ["utils.py", "version", "README.md", "1.0.0", "https://url", "2026-01-01"],
        ):
            command, args = parse_args()
        assert command == "version"
        assert args.readme == Path("README.md")
        assert args.version == "1.0.0"
        assert args.release_url == "https://url"
        assert args.release_date == "2026-01-01"

    def test_parse_sed_command(self):
        """parse_args should parse 'sed' subcommand with pattern and file."""
        with patch("sys.argv", ["utils.py", "sed", "s|old|new|g", "file.txt"]):
            command, args = parse_args()
        assert command == "sed"
        assert args.pattern == "s|old|new|g"
        assert args.file == Path("file.txt")

    def test_parse_no_command_exits(self):
        """parse_args should exit when no subcommand given."""
        with patch("sys.argv", ["utils.py"]), pytest.raises(SystemExit):
            parse_args()

    def test_parse_unknown_command_exits(self):
        """parse_args should exit for an unknown subcommand."""
        with patch("sys.argv", ["utils.py", "bogus"]), pytest.raises(SystemExit):
            parse_args()

    def test_parse_version_missing_args_exits(self):
        """parse_args should exit if 'version' is missing required arguments."""
        with (
            patch("sys.argv", ["utils.py", "version", "README.md"]),
            pytest.raises(SystemExit),
        ):
            parse_args()

    def test_parse_sed_missing_file_exits(self):
        """parse_args should exit if 'sed' is missing the file argument."""
        with (
            patch("sys.argv", ["utils.py", "sed", "s|old|new|g"]),
            pytest.raises(SystemExit),
        ):
            parse_args()


class TestUtilsCLISubprocess:
    """Subprocess smoke tests for vig_utils.utils module."""

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "vig_utils.utils", *args],
            capture_output=True,
            text=True,
        )

    def test_version_e2e(self, tmp_path):
        """Full version update via subprocess."""
        readme = tmp_path / "README.md"
        readme.write_text("- **Version**: [dev](x), 2025-01-01\n")
        result = self._run("version", str(readme), "3.0.0", "https://rel", "2026-06-01")
        assert result.returncode == 0
        assert "[3.0.0]" in readme.read_text()

    def test_sed_e2e(self, tmp_path):
        """Full sed substitution via subprocess."""
        f = tmp_path / "test.txt"
        f.write_text("alpha beta alpha")
        result = self._run("sed", "s|alpha|omega|g", str(f))
        assert result.returncode == 0
        assert f.read_text() == "omega beta omega"


class TestAgentBlocklistHelpers:
    """Tests for blocklist helpers moved into vig_utils.utils."""

    def test_load_blocklist_compiles_and_normalizes(self, tmp_path):
        blocklist_path = tmp_path / "agent-blocklist.toml"
        blocklist_path.write_text(
            "[patterns]\n"
            'trailers = ["^Co-authored-by: .+$"]\n'
            'names = ["CursorAgent", "Claude"]\n'
            'emails = ["CursorAgent@Cursor.com"]\n'
        )

        loaded = load_blocklist(blocklist_path)

        assert len(loaded["trailers"]) == 1
        assert loaded["trailers"][0].pattern == "^Co-authored-by: .+$"
        assert loaded["names"] == ["cursoragent", "claude"]
        assert loaded["emails"] == ["cursoragent@cursor.com"]

    def test_load_blocklist_raises_on_invalid_toml(self, tmp_path):
        blocklist_path = tmp_path / "agent-blocklist.toml"
        blocklist_path.write_text("this is not valid toml {{{}}")
        import tomllib

        with pytest.raises(tomllib.TOMLDecodeError):
            load_blocklist(blocklist_path)

    def test_contains_agent_fingerprint_matches_name(self):
        blocklist = {
            "trailers": [],
            "names": ["cursoragent"],
            "emails": ["cursoragent@cursor.com"],
        }
        match = contains_agent_fingerprint("Generated by CursorAgent", blocklist)
        assert match == "cursoragent"

    def test_contains_agent_fingerprint_matches_email(self):
        blocklist = {
            "trailers": [],
            "names": [],
            "emails": ["cursoragent@cursor.com"],
        }
        match = contains_agent_fingerprint("Contact: cursoragent@cursor.com", blocklist)
        assert match == "cursoragent@cursor.com"

    def test_contains_agent_fingerprint_matches_trailer(self):
        import re

        blocklist = {
            "trailers": [re.compile(r"^Co-authored-by: .+$")],
            "names": [],
            "emails": [],
        }
        match = contains_agent_fingerprint(
            "feat: add feature\n\nCo-authored-by: Bot <bot@example.com>",
            blocklist,
        )
        assert match == "Co-authored-by: Bot <bot@example.com>"

    def test_contains_agent_fingerprint_skips_trailers_when_disabled(self):
        import re

        blocklist = {
            "trailers": [re.compile(r"^Co-authored-by: .+$")],
            "names": [],
            "emails": [],
        }
        match = contains_agent_fingerprint(
            "feat: add feature\n\nCo-authored-by: Bot <bot@example.com>",
            blocklist,
            check_trailers=False,
        )
        assert match is None

    def test_load_blocklist_loads_allow_patterns(self, tmp_path):
        blocklist_path = tmp_path / "agent-blocklist.toml"
        blocklist_path.write_text(
            "[patterns]\n"
            'names = ["cursor"]\n'
            "emails = []\n"
            "trailers = []\n"
            r'allow_patterns = ["\\.[a-zA-Z][\\w-]*/[\\w./-]*"]'
            "\n"
        )
        loaded = load_blocklist(blocklist_path)
        assert "allow_patterns" in loaded
        assert len(loaded["allow_patterns"]) == 1

    def test_contains_fingerprint_passes_plain_prose_name(self):
        """Plain-text mention of a blocked name should NOT trigger (Refs: #274)."""
        blocklist = {
            "trailers": [],
            "names": ["cursor", "copilot"],
            "emails": [],
            "allow_patterns": [],
        }
        assert (
            contains_agent_fingerprint("docs: mention copilot integration", blocklist)
            is None
        )

    def test_contains_fingerprint_passes_prose_in_body(self):
        """PR body discussing tools in prose should NOT trigger (Refs: #274)."""
        blocklist = {
            "trailers": [],
            "names": ["cursor", "copilot"],
            "emails": [],
            "allow_patterns": [],
        }
        body = (
            "This PR updates Cursor docs with plain text "
            "mention of Copilot as comparison."
        )
        assert contains_agent_fingerprint(body, blocklist) is None

    def test_contains_fingerprint_passes_name_near_agent_word(self):
        """Blocked name on a line with 'agent' in a compound term should NOT trigger."""
        blocklist = {
            "trailers": [],
            "names": ["cursor", "copilot"],
            "emails": [],
            "allow_patterns": [],
        }
        text = (
            "The `check-pr-agent-fingerprints` check blocks "
            'mentions of "Cursor" or "Copilot".'
        )
        assert contains_agent_fingerprint(text, blocklist) is None

    def test_contains_fingerprint_blocks_attribution_context(self):
        """Name in an attribution phrase must still be blocked (Refs: #274)."""
        blocklist = {
            "trailers": [],
            "names": ["cursor"],
            "emails": [],
            "allow_patterns": [],
        }
        assert contains_agent_fingerprint("Generated by Cursor", blocklist) == "cursor"

    def test_contains_fingerprint_blocks_authored_by(self):
        blocklist = {
            "trailers": [],
            "names": ["copilot"],
            "emails": [],
            "allow_patterns": [],
        }
        assert (
            contains_agent_fingerprint("Authored by Copilot AI", blocklist) == "copilot"
        )

    def test_contains_fingerprint_strips_allow_patterns(self):
        """allow_patterns text is stripped so dotfile paths don't trigger names."""
        import re

        blocklist = {
            "trailers": [],
            "names": ["cursor"],
            "emails": [],
            "allow_patterns": [re.compile(r"\.[a-zA-Z][\w-]*/[\w./-]*")],
        }
        assert (
            contains_agent_fingerprint("See .claude/skills/ for details", blocklist)
            is None
        )

    def test_contains_fingerprint_strips_allow_then_catches_attribution(self):
        """allow_patterns stripping + attribution context should still catch."""
        import re

        blocklist = {
            "trailers": [],
            "names": ["cursor"],
            "emails": [],
            "allow_patterns": [re.compile(r"\.[a-zA-Z][\w-]*/[\w./-]*")],
        }
        assert (
            contains_agent_fingerprint(
                "See .claude/skills/ for docs generated by Cursor", blocklist
            )
            == "cursor"
        )

    def test_contains_fingerprint_email_still_matched_without_context(self):
        """Email matching stays unconditional (emails are specific enough)."""
        blocklist = {
            "trailers": [],
            "names": [],
            "emails": ["noreply@cursor.com"],
            "allow_patterns": [],
        }
        assert (
            contains_agent_fingerprint("Send to noreply@cursor.com", blocklist)
            == "noreply@cursor.com"
        )


class TestFindRepoRoot:
    """Tests for find_repo_root helper."""

    def test_uses_env_override_when_set(self, tmp_path):
        env_root = tmp_path / "env-root"
        env_root.mkdir()
        with patch.dict(
            "os.environ", {"VIG_UTILS_REPO_ROOT": str(env_root)}, clear=True
        ):
            assert find_repo_root() == env_root.resolve()

    def test_prefers_cwd_when_it_contains_github(self, tmp_path):
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".github").mkdir()
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("vig_utils.utils.Path.cwd", return_value=repo_root),
        ):
            assert find_repo_root() == repo_root.resolve()

    def test_uses_start_path_when_cwd_has_no_github(self, tmp_path):
        cwd = tmp_path / "cwd"
        cwd.mkdir()
        start = tmp_path / "project" / "pkg" / "mod.py"
        start.parent.mkdir(parents=True)
        start.touch()
        (tmp_path / "project" / ".github").mkdir()

        with (
            patch.dict("os.environ", {}, clear=True),
            patch("vig_utils.utils.Path.cwd", return_value=cwd),
        ):
            assert find_repo_root(start=start) == (tmp_path / "project").resolve()

    def test_falls_back_to_cwd_when_no_markers(self, tmp_path):
        cwd = tmp_path / "cwd"
        cwd.mkdir()
        start = tmp_path / "start" / "file.py"
        start.parent.mkdir(parents=True)
        start.touch()

        with (
            patch.dict("os.environ", {}, clear=True),
            patch("vig_utils.utils.Path.cwd", return_value=cwd),
        ):
            assert find_repo_root(start=start) == cwd.resolve()


class TestAgentBlocklistPath:
    """Tests for agent_blocklist_path helper."""

    def test_returns_blocklist_path_under_repo_root(self):
        root = Path("/tmp/fake-repo")
        with patch("vig_utils.utils.find_repo_root", return_value=root):
            assert agent_blocklist_path() == root / ".github" / "agent-blocklist.toml"


class TestSubstituteInFileEdgeCases:
    """Extra edge-case tests for substitute_in_file."""

    def test_single_replacement_when_global_false(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("foo foo foo")
        substitute_in_file(f, "foo", "bar", regex=False, global_replace=False)
        assert f.read_text() == "bar foo foo"

    def test_raises_file_not_found_for_missing_path(self, tmp_path):
        missing = tmp_path / "missing.txt"
        with pytest.raises(FileNotFoundError, match="File not found"):
            substitute_in_file(missing, "a", "b")

    def test_binary_file_decode_error_is_skipped(self, tmp_path):
        file_path = tmp_path / "binary.bin"
        file_path.write_text("content")

        with patch(
            "pathlib.Path.read_text",
            side_effect=UnicodeDecodeError("utf-8", b"", 0, 1, "bad"),
        ):
            substitute_in_file(file_path, "content", "new-content")

        assert file_path.read_text() == "content"
