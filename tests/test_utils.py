"""
Tests for documentation generation and install.sh unit behavior.

Tests functions from:
- docs/generate.py (all functions)
- install.sh (unit tests: dry-run side effects, name sanitization — the
  flag/help surface is covered behaviorally in tests/bats/install.bats)
- host script shebang portability (#687 — pure content checks)

Note: install.sh integration tests (requiring a built container image) live in
tests/test_install_script.py and run under the test-integration CI job.
"""

import importlib.util
import re
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
    docs_path.mkdir(exist_ok=True)
    fake_generate = docs_path / "generate.py"
    fake_generate.write_text("# test helper\n")

    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(content)

    monkeypatch.setattr(generate, "__file__", str(fake_generate))
    return changelog


def _point_generate_docs_to_tmp(monkeypatch, tmp_path: Path, readme_template: str):
    """Point generate_docs() at a temp docs tree with only README.md.j2.

    Creates docs/templates/README.md.j2 and docs/narrative/ under tmp_path and
    repoints ``generate.__file__`` so the real generate_docs() renders into
    tmp_path. The other templates (CONTRIBUTING, TESTING, SKILL_PIPELINE) are
    deliberately absent to exercise the skip-missing-template branch.
    """
    templates_dir = tmp_path / "docs" / "templates"
    templates_dir.mkdir(parents=True)
    (tmp_path / "docs" / "narrative").mkdir()
    (templates_dir / "README.md.j2").write_text(readme_template)

    _point_generate_to_temp_changelog(
        monkeypatch, tmp_path, "# Changelog\n\n## [1.2.3] - 2026-01-01\n"
    )
    # Keep the render hermetic: no `just` subprocess.
    monkeypatch.setattr(generate, "get_just_help", lambda: "recipes listed here")


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

    def test_returns_latest_dated_release(self, tmp_path, monkeypatch):
        """Should return the first dated release, skipping Unreleased."""
        _point_generate_to_temp_changelog(
            monkeypatch,
            tmp_path,
            "# Changelog\n\n"
            "## Unreleased\n\n"
            "## [0.2.0] - 2025-12-10\n\n"
            "## [0.1.0] - 2025-01-01\n",
        )
        assert generate.get_version_from_changelog() == "0.2.0"

    def test_returns_dev_when_no_dated_release(self, tmp_path, monkeypatch):
        """Should return 'dev' when no dated release heading exists."""
        _point_generate_to_temp_changelog(
            monkeypatch,
            tmp_path,
            "# Changelog\n\n## Unreleased\n\nNo releases yet\n",
        )
        assert generate.get_version_from_changelog() == "dev"

    def test_returns_first_version(self, tmp_path, monkeypatch):
        """Should return the first (latest) version found."""
        _point_generate_to_temp_changelog(
            monkeypatch,
            tmp_path,
            "# Changelog\n\n## [2.0.0] - 2026-06-01\n\n## [1.0.0] - 2026-01-01\n",
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

    def test_returns_latest_release_date(self, tmp_path, monkeypatch):
        """Should return the date of the first dated release heading."""
        _point_generate_to_temp_changelog(
            monkeypatch,
            tmp_path,
            "# Changelog\n\n"
            "## Unreleased\n\n"
            "## [0.2.0] - 2025-12-10\n\n"
            "## [0.1.0] - 2025-01-01\n",
        )
        assert generate.get_release_date_from_changelog() == "2025-12-10"

    def test_falls_back_to_now_without_dated_release(self, tmp_path, monkeypatch):
        """Should fall back to a current timestamp when no heading has a date."""
        _point_generate_to_temp_changelog(
            monkeypatch,
            tmp_path,
            "# Changelog\n\n## [0.1.0]\n\nNo date\n",
        )
        result = generate.get_release_date_from_changelog()
        # The fallback is datetime.now().isoformat(timespec="seconds").
        parsed = datetime.fromisoformat(result)
        assert abs((datetime.now() - parsed).total_seconds()) < 60

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
        # Zero-padded YYYY-MM-DD (strptime alone would accept unpadded parts).
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", date), (
            f"Date format is invalid: {date} (expected YYYY-MM-DD)"
        )
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            pytest.fail(f"Date format is invalid: {date} (expected YYYY-MM-DD)")


class TestGenerateDocs:
    """Tests for generate_docs() from docs/generate.py."""

    def test_generate_docs_actual(self):
        """Integration: calling the real generate_docs should succeed."""
        result = generate.generate_docs()
        assert result is True

    def test_skips_missing_templates_and_renders_rest(
        self, tmp_path, monkeypatch, capsys
    ):
        """Missing templates are skipped; present ones still render."""
        _point_generate_docs_to_tmp(
            monkeypatch,
            tmp_path,
            "# {{ project_name }}\nVersion: {{ version }}\n",
        )
        assert generate.generate_docs() is True
        captured = capsys.readouterr()
        assert "Skipping CONTRIBUTING.md.j2" in captured.err
        content = (tmp_path / "README.md").read_text()
        assert "# vigOS Development Environment" in content
        assert "Version: 1.2.3" in content

    def test_include_narrative_strips_front_matter(self, tmp_path, monkeypatch):
        """include_narrative strips YAML front-matter from narrative files."""
        _point_generate_docs_to_tmp(
            monkeypatch, tmp_path, "{{ include_narrative('intro.md') }}\n"
        )
        (tmp_path / "docs" / "narrative" / "intro.md").write_text(
            "---\ntitle: Intro\n---\n\nActual content here.\n"
        )
        assert generate.generate_docs() is True
        content = (tmp_path / "README.md").read_text()
        assert "Actual content here." in content
        assert "title:" not in content

    def test_include_narrative_missing_file_renders_comment(
        self, tmp_path, monkeypatch
    ):
        """include_narrative renders an HTML comment for missing files."""
        _point_generate_docs_to_tmp(
            monkeypatch, tmp_path, "{{ include_narrative('nonexistent.md') }}\n"
        )
        assert generate.generate_docs() is True
        content = (tmp_path / "README.md").read_text()
        assert "<!-- Missing: nonexistent.md -->" in content


def _point_generate_to_temp_skills(
    monkeypatch, tmp_path: Path, skill_files: dict[str, str]
) -> None:
    """Point load_skills() at a temp .claude/skills tree.

    ``skill_files`` maps a skill directory name to its SKILL.md content. An
    empty mapping leaves the skills directory absent to exercise the
    missing-dir branch.
    """
    docs_path = tmp_path / "docs"
    docs_path.mkdir(exist_ok=True)
    fake_generate = docs_path / "generate.py"
    fake_generate.write_text("# test helper\n")

    for name, content in skill_files.items():
        skill_dir = tmp_path / ".claude" / "skills" / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(content)

    monkeypatch.setattr(generate, "__file__", str(fake_generate))


class TestLoadSkills:
    """Unit tests for load_skills() front-matter parsing (#1418)."""

    def test_missing_skills_dir_returns_empty(self, tmp_path, monkeypatch, capsys):
        """An absent .claude/skills directory yields [] plus a stderr warning."""
        _point_generate_to_temp_skills(monkeypatch, tmp_path, {})
        assert generate.load_skills() == []
        assert "Skills directory not found" in capsys.readouterr().err

    def test_parses_front_matter_fields(self, tmp_path, monkeypatch):
        """name/description map to name, slash-trigger, description, group."""
        _point_generate_to_temp_skills(
            monkeypatch,
            tmp_path,
            {
                "code_review": (
                    "---\nname: code_review\ndescription: Review code\n---\nBody\n"
                )
            },
        )
        assert generate.load_skills() == [
            {
                "name": "code_review",
                "trigger": "/code-review",
                "description": "Review code",
                "group": "code",
            }
        ]

    def test_description_defaults_to_empty(self, tmp_path, monkeypatch):
        """A skill without a description still loads, with description ''."""
        _point_generate_to_temp_skills(
            monkeypatch, tmp_path, {"ci_check": "---\nname: ci_check\n---\nBody\n"}
        )
        (skill,) = generate.load_skills()
        assert skill["description"] == ""

    def test_skips_file_without_front_matter(self, tmp_path, monkeypatch):
        """A SKILL.md that does not open with --- is ignored."""
        _point_generate_to_temp_skills(
            monkeypatch, tmp_path, {"code_x": "# just a heading\nname: code_x\n"}
        )
        assert generate.load_skills() == []

    def test_skips_unterminated_front_matter(self, tmp_path, monkeypatch):
        """Front matter without a closing --- is ignored."""
        _point_generate_to_temp_skills(
            monkeypatch, tmp_path, {"code_x": "---\nname: code_x\n"}
        )
        assert generate.load_skills() == []

    def test_skips_front_matter_without_name(self, tmp_path, monkeypatch):
        """Front matter lacking a name key is ignored."""
        _point_generate_to_temp_skills(
            monkeypatch, tmp_path, {"code_x": "---\ndescription: no name\n---\n"}
        )
        assert generate.load_skills() == []

    def test_entries_sorted_by_directory(self, tmp_path, monkeypatch):
        """Skills come back in sorted path order regardless of creation order."""
        _point_generate_to_temp_skills(
            monkeypatch,
            tmp_path,
            {
                "issue_triage": "---\nname: issue_triage\n---\n",
                "ci_check": "---\nname: ci_check\n---\n",
            },
        )
        assert [s["name"] for s in generate.load_skills()] == [
            "ci_check",
            "issue_triage",
        ]


class TestGroupSkills:
    """Unit tests for group_skills() ordering and heading merges (#1418)."""

    @staticmethod
    def _skill(name: str) -> dict:
        return {
            "name": name,
            "trigger": "/" + name.replace("_", "-"),
            "description": "",
            "group": name.split("_")[0],
        }

    def test_groups_follow_declared_order_and_drop_empty(self):
        """Non-empty groups appear in SKILL_GROUP_ORDER order; empty ones drop."""
        groups = generate.group_skills(
            [self._skill("worktree_plan"), self._skill("issue_triage")]
        )
        assert [g["heading"] for g in groups] == [
            "Issue Management",
            "Autonomous Worktree Pipeline",
        ]

    def test_git_and_pr_share_one_heading(self):
        """git and pr prefixes merge into the single Git & PR group."""
        groups = generate.group_skills(
            [self._skill("git_commit"), self._skill("pr_create")]
        )
        (group,) = groups
        assert group["heading"] == "Git & PR (Interactive)"
        assert [s["name"] for s in group["skills"]] == ["git_commit", "pr_create"]

    def test_unknown_prefix_is_dropped(self):
        """A skill whose prefix matches no declared group is not rendered."""
        assert generate.group_skills([self._skill("zzz_orphan")]) == []

    def test_intro_attached_and_prefixes_removed(self):
        """Groups carry their intro text and no internal prefixes set."""
        (group,) = generate.group_skills([self._skill("inception_explore")])
        assert group["intro"] == generate.SKILL_GROUP_INTROS["inception"]
        assert "prefixes" not in group


class TestInstallScriptUnit:
    """Unit tests for install.sh dry-run side effects and name sanitization.

    The flag/help/detection surface is covered behaviorally in
    tests/bats/install.bats; only cases without a bats twin live here.
    """

    @pytest.fixture
    def install_script(self):
        """Path to install.sh."""
        return Path(__file__).resolve().parents[1] / "install.sh"

    def test_script_exists_and_executable(self, install_script):
        """Test install.sh exists and is executable."""
        assert install_script.exists(), "install.sh not found"
        assert install_script.stat().st_mode & 0o111, "install.sh not executable"

    def test_dry_run_creates_no_files(self, install_script, tmp_path):
        """Test --dry-run shows what would be executed without running."""
        result = subprocess.run(
            [str(install_script), "--dry-run", str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"--dry-run failed: {result.stderr}"
        assert "Would execute:" in result.stdout
        # Sole coverage of the no-side-effects contract: dry-run must not
        # scaffold anything.
        assert not (tmp_path / ".devcontainer").exists()
        assert not any(tmp_path.iterdir())

    def test_name_sanitization_trims_trailing_separator(self, install_script):
        """Test --name sanitization trims trailing separators (#1044)."""
        result = subprocess.run(
            [str(install_script), "--dry-run", "--name", "Install-Test-Project-", "."],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(Path(__file__).resolve().parents[1]),
        )
        assert result.returncode == 0, (
            f"install.sh --dry-run --name failed:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "SHORT_NAME=install_test_project" in result.stdout, (
            "Expected sanitized name without trailing underscore in dry-run output"
        )
        assert "SHORT_NAME=install_test_project_" not in result.stdout, (
            "Sanitized name should not end with an underscore"
        )


class TestHostScriptShebangPortability:
    """Assert host-executed scripts use a portable shebang.

    These scripts run on the *host* (not inside the container), so they must
    not hardcode ``#!/bin/bash``: NixOS and other distros that follow the
    Filesystem Hierarchy Standard loosely have no ``/bin/bash``, which makes
    them fail to execute. The portable form ``#!/usr/bin/env bash`` resolves
    ``bash`` via ``PATH`` and works everywhere. Refs #687.

    This is a pure content check — it needs no built container image — so it
    runs in the cheap project-checks lane.
    """

    # Host-executed scripts that must carry the portable shebang. Scoped to
    # the three scripts in issue #687; the broader in-container sweep is out
    # of scope.
    HOST_SCRIPTS = (
        "install.sh",
        "assets/workspace/.devcontainer/scripts/initialize.sh",
        "assets/workspace/.devcontainer/scripts/version-check.sh",
    )

    PORTABLE_SHEBANG = "#!/usr/bin/env bash"

    @pytest.mark.parametrize("rel_path", HOST_SCRIPTS)
    def test_host_script_uses_portable_shebang(self, rel_path):
        """Each host-executed script must start with #!/usr/bin/env bash."""
        project_root = Path(__file__).resolve().parents[1]
        script = project_root / rel_path
        assert script.exists(), f"Expected host script not found: {rel_path}"

        first_line = script.read_text().splitlines()[0]
        assert first_line == self.PORTABLE_SHEBANG, (
            f"{rel_path} must use the portable shebang "
            f"'{self.PORTABLE_SHEBANG}' (NixOS has no /bin/bash), "
            f"but found: {first_line!r}"
        )
