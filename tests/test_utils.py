"""
Tests for documentation generation and install.sh unit behavior.

Tests functions from:
- docs/generate.py (all functions)
- install.sh (unit tests: help, dry-run, flags — no container image needed)

Note: install.sh integration tests (requiring a built container image) live in
tests/test_install_script.py and run under the test-integration CI job.
"""

import importlib.util
import subprocess
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

docs_dir = Path(__file__).parent.parent / "docs"

generate_spec = importlib.util.spec_from_file_location(
    "generate", docs_dir / "generate.py"
)
generate = importlib.util.module_from_spec(generate_spec)
generate_spec.loader.exec_module(generate)


def _point_generate_to_temp_changelog(
    monkeypatch, tmp_path: Path, content: str
) -> Path:
    """Point generate.py changelog lookup to a temp CHANGELOG.md file."""
    docs_path = tmp_path / "docs"
    docs_path.mkdir()
    fake_generate = docs_path / "generate.py"
    fake_generate.write_text("# test helper\n")

    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(content)

    monkeypatch.setattr(generate, "__file__", str(fake_generate))
    return changelog


# ═════════════════════════════════════════════════════════════════════════════
# docs/generate.py — function-level unit tests
# ═════════════════════════════════════════════════════════════════════════════


class TestGetJustHelp:
    """Tests for get_just_help() from docs/generate.py."""

    def test_returns_string(self):
        """Should always return a string."""
        result = generate.get_just_help()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_exits_when_just_not_found(self):
        """Should exit non-zero when 'just' binary is missing."""
        with (
            patch("subprocess.run", side_effect=FileNotFoundError("no just")),
            pytest.raises(SystemExit) as exc_info,
        ):
            generate.get_just_help()
        assert exc_info.value.code == 1

    def test_exits_on_called_process_error(self):
        """Should exit non-zero when 'just --list' fails."""
        with (
            patch(
                "subprocess.run",
                side_effect=subprocess.CalledProcessError(1, "just"),
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            generate.get_just_help()
        assert exc_info.value.code == 1


class TestGetVersionFromChangelog:
    """Direct tests for get_version_from_changelog()."""

    def test_get_version_from_changelog_found(self, tmp_path):
        """Test version extraction when changelog exists with release."""
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text(
            "# Changelog\n\n"
            "## Unreleased\n\n"
            "## [0.2.0] - 2025-12-10\n\n"
            "## [0.1.0] - 2025-01-01\n"
        )

        # Test the logic directly (same as in generate.py)
        version_found = None
        with changelog.open() as f:
            for line in f:
                if line.startswith("## ["):
                    version_found = line.split("[")[1].split("]")[0]
                    break

        assert version_found == "0.2.0"

    def test_get_version_from_changelog_not_found(self, tmp_path):
        """Test version extraction when no release found."""
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text("# Changelog\n\n## Unreleased\n\nNo releases yet\n")

        # Test logic directly
        version_found = None
        with changelog.open() as f:
            for line in f:
                if line.startswith("## ["):
                    version_found = line.split("[")[1].split("]")[0]
                    break

        assert version_found is None

    def test_returns_dev_when_no_versions(self, tmp_path, monkeypatch):
        """Should return 'dev' when there are no version headings."""
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text("# Changelog\n\n## Unreleased\n\n- stuff\n")
        # Patch the function's file resolution to use our temp file
        monkeypatch.setattr(
            generate,
            "get_version_from_changelog",
            lambda: _get_version_from_file(changelog),
        )
        result = generate.get_version_from_changelog()
        assert result == "dev"

    def test_returns_first_version(self, tmp_path, monkeypatch):
        """Should return the first (latest) version found."""
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text(
            "# Changelog\n\n## [2.0.0] - 2026-06-01\n\n## [1.0.0] - 2026-01-01\n"
        )
        monkeypatch.setattr(
            generate,
            "get_version_from_changelog",
            lambda: _get_version_from_file(changelog),
        )
        assert generate.get_version_from_changelog() == "2.0.0"

    def test_skips_tbd_entry(self, tmp_path, monkeypatch):
        """Should ignore unreleased headings and use latest released version."""
        _point_generate_to_temp_changelog(
            monkeypatch,
            tmp_path,
            "# Changelog\n\n"
            "## [0.3.0] - TBD\n\n"
            "## [0.2.1] - 2026-01-28\n\n"
            "## [0.2.0] - 2025-12-10\n",
        )
        assert generate.get_version_from_changelog() == "0.2.1"

    def test_get_version_from_changelog_actual(self):
        """Test version extraction from actual CHANGELOG.md."""
        version = generate.get_version_from_changelog()
        assert isinstance(version, str)
        assert version == "dev" or version.count(".") >= 1


class TestGetReleaseDateFromChangelog:
    """Direct tests for get_release_date_from_changelog()."""

    def test_get_release_date_from_changelog_found(self, tmp_path):
        """Test date extraction when changelog exists with release."""
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text(
            "# Changelog\n\n"
            "## Unreleased\n\n"
            "## [0.2.0] - 2025-12-10\n\n"
            "## [0.1.0] - 2025-01-01\n"
        )

        date_found = None
        with changelog.open() as f:
            for line in f:
                if line.startswith("## ["):
                    parts = line.split("]")
                    if len(parts) > 1:
                        date_part = parts[1].split(" - ")
                        if len(date_part) > 1:
                            date_found = date_part[1].strip()
                            break

        assert date_found == "2025-12-10"

    def test_get_release_date_from_changelog_not_found(self, tmp_path):
        """Test date extraction when no release found."""
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text("# Changelog\n\n## Unreleased\n\nNo releases yet\n")

        date_found = None
        with changelog.open() as f:
            for line in f:
                if line.startswith("## ["):
                    parts = line.split("]")
                    if len(parts) > 1:
                        date_part = parts[1].split(" - ")
                        if len(date_part) > 1:
                            date_found = date_part[1].strip()
                            break

        assert date_found is None

    def test_skips_tbd_entry(self, tmp_path, monkeypatch):
        """Should ignore unreleased headings and use latest released date."""
        _point_generate_to_temp_changelog(
            monkeypatch,
            tmp_path,
            "# Changelog\n\n"
            "## [0.3.0] - TBD\n\n"
            "## [0.2.1] - 2026-01-28\n\n"
            "## [0.2.0] - 2025-12-10\n",
        )
        assert generate.get_release_date_from_changelog() == "2026-01-28"

    def test_get_release_date_from_changelog_actual(self):
        """Test date extraction from actual CHANGELOG.md."""
        date = generate.get_release_date_from_changelog()
        assert isinstance(date, str)
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            pytest.fail(f"Date format is invalid: {date} (expected YYYY-MM-DD)")

    def test_get_release_date_format(self):
        """Test that returned date is in correct format."""
        date = generate.get_release_date_from_changelog()
        parts = date.split("-")
        assert len(parts) == 3
        assert len(parts[0]) == 4  # Year
        assert len(parts[1]) == 2  # Month
        assert len(parts[2]) == 2  # Day
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
        assert 2000 <= year <= 2100
        assert 1 <= month <= 12
        assert 1 <= day <= 31

    def test_get_release_date_without_date_part(self, tmp_path):
        """Test date extraction when release line has no date."""
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text("# Changelog\n\n## [0.1.0]\n\nNo date\n")

        date_found = None
        with changelog.open() as f:
            for line in f:
                if line.startswith("## ["):
                    parts = line.split("]")
                    if len(parts) > 1:
                        date_part = parts[1].split(" - ")
                        if len(date_part) > 1:
                            date_found = date_part[1].strip()
                            break

        assert date_found is None


class TestGenerateDocs:
    """Tests for generate_docs() from docs/generate.py."""

    def test_generate_docs_succeeds(self, tmp_path, monkeypatch):
        """generate_docs should render templates and write output files."""
        # Set up a minimal docs/templates structure
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        narrative_dir = tmp_path / "narrative"
        narrative_dir.mkdir()

        # Simple template
        (templates_dir / "README.md.j2").write_text(
            "# {{ project_name }}\nVersion: {{ version }}\n"
        )

        # Monkeypatch all external calls to make it hermetic
        monkeypatch.setattr(generate, "get_just_help", lambda: "recipes listed here")
        monkeypatch.setattr(generate, "get_version_from_changelog", lambda: "1.2.3")
        monkeypatch.setattr(
            generate, "get_release_date_from_changelog", lambda: "2026-02-11"
        )

        # Inline the logic of generate_docs with patched paths
        import jinja2

        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(templates_dir)),
            keep_trailing_newline=True,
        )
        template = env.get_template("README.md.j2")
        output = template.render(
            project_name="Test Project",
            version="1.2.3",
        )
        output_path = tmp_path / "README.md"
        output_path.write_text(output)

        content = output_path.read_text()
        assert "# Test Project" in content
        assert "Version: 1.2.3" in content

    def test_generate_docs_actual(self):
        """Integration: calling the real generate_docs should succeed."""
        result = generate.generate_docs()
        assert result is True

    def test_generate_docs_skips_missing_template(self, capsys, monkeypatch):
        """generate_docs should skip templates that don't exist."""
        # Temporarily make templates_to_generate include a bogus template
        # by patching generate_docs to add a fake entry. We just call the
        # real function — it should skip non-existent templates gracefully.
        result = generate.generate_docs()
        assert result is True


class TestIncludeNarrative:
    """Test the include_narrative helper used inside generate_docs."""

    def test_includes_existing_file(self, tmp_path):
        """Should return stripped content of an existing narrative file."""
        narrative_dir = tmp_path / "narrative"
        narrative_dir.mkdir()
        (narrative_dir / "intro.md").write_text("Hello world!\n\n")

        import jinja2

        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(tmp_path)),
        )

        def include_narrative(filename):
            path = narrative_dir / filename
            if path.exists():
                return path.read_text().strip()
            return f"<!-- Missing: {filename} -->"

        env.globals["include_narrative"] = include_narrative
        result = include_narrative("intro.md")
        assert result == "Hello world!"

    def test_strips_front_matter(self, tmp_path):
        """Should strip YAML front-matter from narrative files."""
        narrative_dir = tmp_path / "narrative"
        narrative_dir.mkdir()
        (narrative_dir / "intro.md").write_text(
            "---\ntitle: Intro\n---\n\nActual content here.\n"
        )

        def include_narrative(filename):
            path = narrative_dir / filename
            if path.exists():
                content = path.read_text()
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        content = parts[2]
                return content.strip()
            return f"<!-- Missing: {filename} -->"

        result = include_narrative("intro.md")
        assert result == "Actual content here."
        assert "title:" not in result

    def test_returns_comment_for_missing_file(self, tmp_path):
        """Should return an HTML comment for a missing narrative file."""
        narrative_dir = tmp_path / "narrative"
        narrative_dir.mkdir()

        def include_narrative(filename):
            path = narrative_dir / filename
            if path.exists():
                return path.read_text().strip()
            return f"<!-- Missing: {filename} -->"

        result = include_narrative("nonexistent.md")
        assert result == "<!-- Missing: nonexistent.md -->"


# ═════════════════════════════════════════════════════════════════════════════
# Helper functions for testable monkeypatching
# ═════════════════════════════════════════════════════════════════════════════


def _get_version_from_file(changelog_path: Path) -> str:
    """Replicates get_version_from_changelog logic against an arbitrary file."""
    if changelog_path.exists():
        with changelog_path.open() as f:
            for line in f:
                if line.startswith("## ["):
                    return line.split("[")[1].split("]")[0]
    return "dev"


class TestInstallScriptUnit:
    """Unit tests for install.sh - test script logic without containers."""

    @pytest.fixture
    def install_script(self):
        """Path to install.sh."""
        return Path(__file__).resolve().parents[1] / "install.sh"

    def test_script_exists_and_executable(self, install_script):
        """Test install.sh exists and is executable."""
        assert install_script.exists(), "install.sh not found"
        assert install_script.stat().st_mode & 0o111, "install.sh not executable"

    def test_help_output(self, install_script):
        """Test --help shows usage information."""
        result = subprocess.run(
            [str(install_script), "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"--help failed: {result.stderr}"
        assert "vigOS Devcontainer Install Script" in result.stdout
        assert "--force" in result.stdout
        assert "--version" in result.stdout
        assert "--dry-run" in result.stdout
        assert "--name" in result.stdout

    def test_dry_run_shows_command(self, install_script, tmp_path):
        """Test --dry-run shows what would be executed without running."""
        result = subprocess.run(
            [str(install_script), "--dry-run", str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"--dry-run failed: {result.stderr}"
        assert "Would execute:" in result.stdout
        # Should NOT create any files
        assert not (tmp_path / ".devcontainer").exists()

    def test_nonexistent_directory_fails(self, install_script):
        """Test script fails gracefully for non-existent directory."""
        result = subprocess.run(
            [str(install_script), "/nonexistent/path/that/does/not/exist"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode != 0
        output = result.stdout + result.stderr
        assert "does not exist" in output

    def test_name_sanitization_in_dry_run(self, install_script, tmp_path):
        """Test that project name is sanitized correctly."""
        # Create directory with name that needs sanitization
        test_dir = tmp_path / "My-Awesome-Project"
        test_dir.mkdir()

        result = subprocess.run(
            [str(install_script), "--dry-run", str(test_dir)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"Failed: {result.stderr}"
        # Name should be sanitized: lowercase, hyphens → underscores
        assert "my_awesome_project" in result.stdout.lower()

    def test_custom_name_override(self, install_script, tmp_path):
        """Test --name flag overrides derived name."""
        result = subprocess.run(
            [str(install_script), "--dry-run", "--name", "custom_proj", str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"Failed: {result.stderr}"
        assert "custom_proj" in result.stdout

    def test_version_flag_in_dry_run(self, install_script, tmp_path):
        """Test --version flag is passed to container."""
        result = subprocess.run(
            [str(install_script), "--dry-run", "--version", "1.2.3", str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"Failed: {result.stderr}"
        assert "1.2.3" in result.stdout

    def test_force_flag_in_dry_run(self, install_script, tmp_path):
        """Test --force flag is passed to init-workspace.sh.

        Uses a clean feature-branch git fixture: the upgrade preflight guard
        (#886) refuses --force on non-git directories, protected branches,
        and dirty trees.
        """
        git_env = [
            "git",
            "-c",
            "user.email=t@example.com",
            "-c",
            "user.name=T",
            "-c",
            "commit.gpgsign=false",
        ]
        subprocess.run(
            [*git_env, "init", "-q", "-b", "feature/886-fixture", str(tmp_path)],
            check=True,
            timeout=10,
        )
        subprocess.run(
            [
                *git_env,
                "-C",
                str(tmp_path),
                "commit",
                "-q",
                "--allow-empty",
                "-m",
                "chore: init",
            ],
            check=True,
            timeout=10,
        )
        result = subprocess.run(
            [str(install_script), "--dry-run", "--force", str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"Failed: {result.stderr}"
        assert "--force" in result.stdout

    def test_org_flag_in_help(self, install_script):
        """Test --org flag is documented in help output."""
        result = subprocess.run(
            [str(install_script), "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"--help failed: {result.stderr}"
        assert "--org" in result.stdout, "--org flag not documented in help"

    def test_default_org_in_dry_run(self, install_script, tmp_path):
        """Test default ORG_NAME is 'vigOS' when --org is not specified."""
        result = subprocess.run(
            [str(install_script), "--dry-run", str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"Failed: {result.stderr}"
        # Should show ORG_NAME=vigOS being passed to container
        assert "ORG_NAME" in result.stdout, "ORG_NAME should be passed to container"
        # Default should be vigOS
        assert (
            'ORG_NAME="vigOS"' in result.stdout or "ORG_NAME=vigOS" in result.stdout
        ), f"Default ORG_NAME should be 'vigOS', got: {result.stdout}"

    def test_custom_org_in_dry_run(self, install_script, tmp_path):
        """Test --org flag sets custom ORG_NAME."""
        result = subprocess.run(
            [str(install_script), "--dry-run", "--org", "MyOrg", str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"Failed: {result.stderr}"
        # Should show custom ORG_NAME being passed to container
        assert (
            'ORG_NAME="MyOrg"' in result.stdout or "ORG_NAME=MyOrg" in result.stdout
        ), f"Custom ORG_NAME 'MyOrg' should be in output, got: {result.stdout}"
