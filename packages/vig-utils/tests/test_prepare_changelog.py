"""
Tests for vig_utils.prepare_changelog.

Comprehensive coverage including:
- Unit tests for all functions (import-based, direct function calls)
- CLI command handler tests (stdout/exit behavior)
- Subprocess integration tests (end-to-end CLI verification)
- Edge cases, validation, and error handling

Tests are organized by function under test, from low-level helpers up to the CLI layer.
"""

import os
import re
import shutil
import subprocess
from unittest.mock import patch

import pytest
from vig_utils.prepare_changelog import (
    STANDARD_SECTIONS,
    cmd_finalize,
    cmd_prepare,
    cmd_reset,
    cmd_reset_version,
    cmd_unprepare,
    cmd_validate,
    create_new_changelog,
    extract_unreleased_content,
    finalize_release_date,
    main,
    prepare_changelog,
    reset_unreleased,
    reset_version_to_tbd,
    unprepare_changelog,
    validate_changelog,
)

# Find the CLI entry point installed by the package
ENTRY_POINT = shutil.which("prepare-changelog")

# Owner/repo slug for finalize_release_date tests (not hardcoded in production code)
_FINALIZE_TEST_REPO = "vig-os/devcontainer"

# ─── Test data constants ──────────────────────────────────────────────────────

BASIC_CHANGELOG = """\
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- New feature X
- New feature Y

### Changed

- Updated component Z

### Deprecated

### Removed

### Fixed

- Bug fix A
- Bug fix B

### Security

## [0.2.0] - 2026-01-01

### Added

- Previous feature
"""

EMPTY_SECTIONS_CHANGELOG = """\
# Changelog

## Unreleased

### Added

- New feature

### Changed

### Deprecated

### Removed

### Fixed

### Security

## [0.2.0] - 2026-01-01

### Added

- Old feature
"""

MINIMAL_CHANGELOG = """\
# Changelog

## Unreleased

### Added

- Single feature

## [0.1.0] - 2025-12-01

### Added

- Initial release
"""

NO_UNRELEASED_CHANGELOG = """\
# Changelog

## [0.2.0] - 2026-01-01

### Added

- Old feature
"""

EMPTY_UNRELEASED_CHANGELOG = """\
# Changelog

## Unreleased

### Added

### Changed

### Fixed

## [0.2.0] - 2026-01-01

### Added

- Old feature
"""

MULTILINE_BULLETS_CHANGELOG = """\
# Changelog

## Unreleased

### Added

- New feature with
  multiple lines of description
  and even more details

## [0.1.0] - 2025-01-01
"""

NESTED_BULLETS_CHANGELOG = """\
# Changelog

## Unreleased

### Added

- Main feature
  - Sub-feature A
  - Sub-feature B

## [0.1.0] - 2025-01-01
"""

UNRELEASED_ONLY_CHANGELOG = """\
# Changelog

## Unreleased

### Added

- Brand new feature

### Fixed

- Important bugfix
"""

RELEASED_ONLY_CHANGELOG = """\
# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] - 2026-02-06

### Added

- Released feature

## [0.2.0] - 2026-01-01

### Added

- Old feature
"""

CHANGELOG_WITH_TBD = """\
# Changelog

## Unreleased

### Added

### Changed

### Deprecated

### Removed

### Fixed

### Security

## [1.0.0] - TBD

### Added

- Feature X
- Feature Y

### Fixed

- Bug A

## [0.2.0] - 2026-01-01

### Added

- Old feature
"""

MULTIPLE_TBD_CHANGELOG = """\
# Changelog

## Unreleased

### Added

## [2.0.0] - TBD

### Added

- Feature Z

## [1.0.0] - TBD

### Added

- Feature X

## [0.1.0] - 2025-12-01

### Added

- Initial
"""

ALL_SECTIONS_CHANGELOG = """\
# Changelog

## Unreleased

### Added

- New feature

### Changed

- Changed component

### Deprecated

- Old API deprecated

### Removed

- Removed legacy module

### Fixed

- Fixed crash

### Security

- Patched vulnerability

## [0.1.0] - 2025-01-01
"""


# ─── Shared fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def basic_changelog():
    return BASIC_CHANGELOG


@pytest.fixture
def changelog_with_tbd():
    return CHANGELOG_WITH_TBD


# ═════════════════════════════════════════════════════════════════════════════
# STANDARD_SECTIONS constant
# ═════════════════════════════════════════════════════════════════════════════


class TestStandardSections:
    """Verify the STANDARD_SECTIONS constant."""

    def test_contains_all_keepachangelog_sections(self):
        """STANDARD_SECTIONS should include the 6 Keep a Changelog categories."""
        expected = ["Added", "Changed", "Deprecated", "Removed", "Fixed", "Security"]
        assert expected == STANDARD_SECTIONS

    def test_is_list_of_strings(self):
        """STANDARD_SECTIONS should be a list of strings."""
        assert isinstance(STANDARD_SECTIONS, list)
        for section in STANDARD_SECTIONS:
            assert isinstance(section, str)


# ═════════════════════════════════════════════════════════════════════════════
# extract_unreleased_content
# ═════════════════════════════════════════════════════════════════════════════


class TestExtractUnreleasedContent:
    """Unit tests for extract_unreleased_content()."""

    def test_basic_extraction(self):
        """Should extract sections that have bullet content."""
        sections = extract_unreleased_content(BASIC_CHANGELOG)
        assert "Added" in sections
        assert "Changed" in sections
        assert "Fixed" in sections
        assert "New feature X" in sections["Added"]
        assert "New feature Y" in sections["Added"]
        assert "Updated component Z" in sections["Changed"]
        assert "Bug fix A" in sections["Fixed"]

    def test_empty_sections_excluded(self):
        """Sections without bullet content should be excluded."""
        sections = extract_unreleased_content(BASIC_CHANGELOG)
        assert "Deprecated" not in sections
        assert "Removed" not in sections
        assert "Security" not in sections

    def test_all_six_sections_populated(self):
        """Should extract all 6 sections when each has content."""
        sections = extract_unreleased_content(ALL_SECTIONS_CHANGELOG)
        assert len(sections) == 6
        for name in STANDARD_SECTIONS:
            assert name in sections

    def test_multiline_bullets(self):
        """Should preserve multi-line bullet point formatting."""
        sections = extract_unreleased_content(MULTILINE_BULLETS_CHANGELOG)
        assert "Added" in sections
        assert "multiple lines of description" in sections["Added"]
        assert "and even more details" in sections["Added"]

    def test_nested_bullets(self):
        """Should preserve nested/indented bullets."""
        sections = extract_unreleased_content(NESTED_BULLETS_CHANGELOG)
        assert "Added" in sections
        assert "Main feature" in sections["Added"]
        assert "Sub-feature A" in sections["Added"]
        assert "Sub-feature B" in sections["Added"]

    def test_raises_when_no_unreleased_section(self):
        """Should raise ValueError when there is no Unreleased heading."""
        with pytest.raises(ValueError, match="No.*Unreleased"):
            extract_unreleased_content(NO_UNRELEASED_CHANGELOG)

    def test_does_not_capture_next_version_content(self):
        """Content from a following version section must not leak in."""
        sections = extract_unreleased_content(MINIMAL_CHANGELOG)
        assert "Added" in sections
        assert "Single feature" in sections["Added"]
        assert "Initial release" not in sections["Added"]

    def test_returns_empty_dict_for_empty_unreleased(self):
        """Should return empty dict when Unreleased has no bullet points."""
        sections = extract_unreleased_content(EMPTY_UNRELEASED_CHANGELOG)
        assert sections == {}

    def test_whitespace_only_lines_are_not_content(self):
        """Sections with only whitespace lines should be treated as empty."""
        changelog = """\
# Changelog

## Unreleased

### Added

   \t

### Fixed

- Real fix
"""
        sections = extract_unreleased_content(changelog)
        assert "Added" not in sections
        assert "Fixed" in sections

    def test_single_bullet_extraction(self):
        """Should work with exactly one bullet under one heading."""
        changelog = """\
# Changelog

## Unreleased

### Security

- CVE-2026-0001 patched
"""
        sections = extract_unreleased_content(changelog)
        assert list(sections.keys()) == ["Security"]
        assert "CVE-2026-0001" in sections["Security"]

    def test_inline_hash_markers_not_truncated(self):
        """Inline ## or ### in backticks must not truncate content (sync-issues-action #18)."""
        changelog = """\
# Changelog

## Unreleased

### Fixed

- Corrected heading hierarchy: promoted from `##` to `#`
- Fixed indentation in `### subsection` headers
- Third fix unrelated to headings
- Another entry mentioning `##` in a sentence
- Fifth fix at the end

### Added

- New feature
"""
        sections = extract_unreleased_content(changelog)
        assert "Fixed" in sections
        assert "Corrected heading hierarchy" in sections["Fixed"]
        assert "Fixed indentation" in sections["Fixed"]
        assert "Third fix" in sections["Fixed"]
        assert "Another entry mentioning" in sections["Fixed"]
        assert "Fifth fix at the end" in sections["Fixed"]
        assert "Added" in sections
        assert "New feature" in sections["Added"]


# ═════════════════════════════════════════════════════════════════════════════
# create_new_changelog
# ═════════════════════════════════════════════════════════════════════════════


class TestCreateNewChangelog:
    """Unit tests for create_new_changelog()."""

    def test_basic_structure(self):
        """Result should contain header, Unreleased, and version section."""
        result = create_new_changelog("1.0.0", {"Added": "- Feature\n"}, "")
        assert "# Changelog" in result
        assert "## Unreleased" in result
        assert "## [1.0.0] - TBD" in result

    def test_header_content(self):
        """Should include the Keep a Changelog / SemVer boilerplate."""
        result = create_new_changelog("1.0.0", {}, "")
        assert "Keep a Changelog" in result
        assert "Semantic Versioning" in result

    def test_unreleased_before_version(self):
        """Unreleased section must appear before the version section."""
        result = create_new_changelog("2.0.0", {"Fixed": "- Fix\n"}, "")
        assert result.index("## Unreleased") < result.index("## [2.0.0] - TBD")

    def test_all_standard_sections_in_unreleased(self):
        """Fresh Unreleased should contain all 6 standard sub-headings."""
        result = create_new_changelog("1.0.0", {}, "")
        unreleased_idx = result.index("## Unreleased")
        # There shouldn't be a version section key marker yet; search up to version
        version_idx = result.index("## [1.0.0]")
        unreleased_block = result[unreleased_idx:version_idx]
        for section in STANDARD_SECTIONS:
            assert f"### {section}" in unreleased_block

    def test_only_populated_sections_in_version(self):
        """Version section should only include sections that have content."""
        old = {"Added": "- Feature A\n", "Fixed": "- Bug B\n"}
        result = create_new_changelog("1.0.0", old, "")
        version_idx = result.index("## [1.0.0]")
        version_block = result[version_idx:]
        assert "### Added" in version_block
        assert "### Fixed" in version_block
        assert "### Changed" not in version_block
        assert "### Deprecated" not in version_block

    def test_empty_old_sections(self):
        """Version section with no content should still have the heading."""
        result = create_new_changelog("1.0.0", {}, "")
        assert "## [1.0.0] - TBD" in result

    def test_preserves_rest_of_changelog(self):
        """Content after old Unreleased should be appended at the end."""
        rest = "## [0.9.0] - 2023-12-01\n\n### Added\n\n- Old feature\n"
        result = create_new_changelog("1.0.0", {}, rest)
        assert "## [0.9.0] - 2023-12-01" in result
        assert "Old feature" in result

    def test_sections_follow_standard_order(self):
        """Version sections should respect STANDARD_SECTIONS ordering."""
        old = {
            "Security": "- Sec fix\n",
            "Added": "- Feature\n",
            "Fixed": "- Bug\n",
        }
        result = create_new_changelog("1.0.0", old, "")
        version_idx = result.index("## [1.0.0]")
        version_block = result[version_idx:]
        added_pos = version_block.index("### Added")
        fixed_pos = version_block.index("### Fixed")
        security_pos = version_block.index("### Security")
        assert added_pos < fixed_pos < security_pos

    def test_multiple_bullets_preserved(self):
        """Multiple bullets under a section must all appear."""
        old = {"Added": "- Feature A\n- Feature B\n- Feature C\n"}
        result = create_new_changelog("1.0.0", old, "")
        assert "- Feature A" in result
        assert "- Feature B" in result
        assert "- Feature C" in result


# ═════════════════════════════════════════════════════════════════════════════
# validate_changelog
# ═════════════════════════════════════════════════════════════════════════════


class TestValidateChangelog:
    """Unit tests for validate_changelog()."""

    def test_passes_with_content(self, tmp_path):
        """Should return (True, True) when Unreleased has bullets."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(BASIC_CHANGELOG)
        has_section, has_content = validate_changelog(str(f))
        assert has_section is True
        assert has_content is True

    def test_fails_missing_unreleased(self, tmp_path):
        """Should return (False, ...) when no Unreleased heading."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(NO_UNRELEASED_CHANGELOG)
        has_section, has_content = validate_changelog(str(f))
        assert has_section is False

    def test_fails_empty_unreleased(self, tmp_path):
        """Should return (True, False) when Unreleased has no bullets."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(EMPTY_UNRELEASED_CHANGELOG)
        has_section, has_content = validate_changelog(str(f))
        assert has_section is True
        assert has_content is False

    def test_raises_for_missing_file(self, tmp_path):
        """Should raise FileNotFoundError for nonexistent file."""
        with pytest.raises(FileNotFoundError, match="CHANGELOG not found"):
            validate_changelog(str(tmp_path / "nope.md"))

    def test_minimal_changelog(self, tmp_path):
        """Should pass for a minimal changelog with one bullet."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(MINIMAL_CHANGELOG)
        has_section, has_content = validate_changelog(str(f))
        assert has_section is True
        assert has_content is True

    def test_unreleased_with_only_headers(self, tmp_path):
        """Unreleased with sub-headings but no bullets has no content."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text("""\
# Changelog

## Unreleased

### Added

### Changed

### Fixed
""")
        _, has_content = validate_changelog(str(f))
        assert has_content is False

    def test_unreleased_at_end_of_file(self, tmp_path):
        """Unreleased with content at EOF (no following version) should pass."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(UNRELEASED_ONLY_CHANGELOG)
        has_section, has_content = validate_changelog(str(f))
        assert has_section is True
        assert has_content is True


# ═════════════════════════════════════════════════════════════════════════════
# prepare_changelog
# ═════════════════════════════════════════════════════════════════════════════


class TestPrepareChangelog:
    """Unit tests for prepare_changelog()."""

    # ── Happy path ────────────────────────────────────────────────────────

    def test_creates_version_section(self, tmp_path, basic_changelog):
        """Should create [version] - TBD section."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(basic_changelog)
        prepare_changelog("1.0.0", str(f))
        assert "## [1.0.0] - TBD" in f.read_text()

    def test_moves_content_to_version(self, tmp_path, basic_changelog):
        """Content from Unreleased should appear under the version heading."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(basic_changelog)
        prepare_changelog("1.0.0", str(f))
        content = f.read_text()
        version_start = content.find("## [1.0.0] - TBD")
        version_end = content.find("## [0.2.0]")
        version_section = content[version_start:version_end]
        for item in [
            "New feature X",
            "New feature Y",
            "Updated component Z",
            "Bug fix A",
            "Bug fix B",
        ]:
            assert item in version_section

    def test_creates_fresh_unreleased(self, tmp_path, basic_changelog):
        """Fresh Unreleased section should contain all 6 headings and no bullets."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(basic_changelog)
        prepare_changelog("1.0.0", str(f))
        content = f.read_text()
        unreleased_block = content[
            content.find("## Unreleased") : content.find("## [1.0.0]")
        ]
        for section in STANDARD_SECTIONS:
            assert f"### {section}" in unreleased_block
        assert "- " not in unreleased_block

    def test_removes_empty_sections_from_version(self, tmp_path):
        """Empty sections should not appear in the version block."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(EMPTY_SECTIONS_CHANGELOG)
        prepare_changelog("1.0.0", str(f))
        content = f.read_text()
        version_start = content.find("## [1.0.0] - TBD")
        version_end = content.find("## [0.2.0]")
        version_section = content[version_start:version_end]
        assert "### Added" in version_section
        assert "- New feature" in version_section
        for empty_sec in ["Changed", "Deprecated", "Removed", "Fixed", "Security"]:
            assert f"### {empty_sec}" not in version_section

    def test_preserves_previous_versions(self, tmp_path, basic_changelog):
        """Previous version sections should remain untouched."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(basic_changelog)
        prepare_changelog("1.0.0", str(f))
        content = f.read_text()
        assert "## [0.2.0] - 2026-01-01" in content
        assert "- Previous feature" in content

    def test_returns_old_sections(self, tmp_path, basic_changelog):
        """prepare_changelog should return the dict of moved sections."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(basic_changelog)
        sections = prepare_changelog("1.0.0", str(f))
        assert isinstance(sections, dict)
        assert "Added" in sections
        assert "Changed" in sections
        assert "Fixed" in sections

    def test_returns_empty_dict_for_empty_unreleased(self, tmp_path):
        """Should return {} when Unreleased has no content."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(EMPTY_UNRELEASED_CHANGELOG)
        sections = prepare_changelog("1.0.0", str(f))
        assert sections == {}

    def test_unreleased_only_no_prior_versions(self, tmp_path):
        """Should work when there are no prior version sections."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(UNRELEASED_ONLY_CHANGELOG)
        prepare_changelog("1.0.0", str(f))
        content = f.read_text()
        assert "## [1.0.0] - TBD" in content
        assert "- Brand new feature" in content
        assert "- Important bugfix" in content
        assert content.index("## Unreleased") < content.index("## [1.0.0]")

    def test_single_unreleased_heading_after_prepare(self, tmp_path, basic_changelog):
        """There should be exactly one Unreleased heading after prepare."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(basic_changelog)
        prepare_changelog("1.0.0", str(f))
        assert f.read_text().count("## Unreleased") == 1

    # ── Multiline / nested content ────────────────────────────────────────

    def test_preserves_multiline_bullets(self, tmp_path):
        """Multi-line bullet points should be preserved after prepare."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(MULTILINE_BULLETS_CHANGELOG)
        prepare_changelog("1.0.0", str(f))
        content = f.read_text()
        assert "multiple lines of description" in content
        assert "and even more details" in content

    def test_preserves_nested_bullets(self, tmp_path):
        """Nested bullet points should be preserved after prepare."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(NESTED_BULLETS_CHANGELOG)
        prepare_changelog("1.0.0", str(f))
        content = f.read_text()
        assert "- Main feature" in content
        assert "- Sub-feature A" in content
        assert "- Sub-feature B" in content

    # ── Version validation ────────────────────────────────────────────────

    def test_rejects_invalid_semver(self, tmp_path, basic_changelog):
        """Should raise ValueError for non-semver strings."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(basic_changelog)
        with pytest.raises(ValueError, match="Invalid semantic version"):
            prepare_changelog("1.0.0.4", str(f))

    def test_rejects_v_prefix(self, tmp_path, basic_changelog):
        """Should raise ValueError for 'v' prefixed versions."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(basic_changelog)
        with pytest.raises(ValueError, match="Invalid semantic version"):
            prepare_changelog("v1.0.0", str(f))

    def test_rejects_prerelease(self, tmp_path, basic_changelog):
        """Should raise ValueError for pre-release suffixed versions."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(basic_changelog)
        with pytest.raises(ValueError, match="Invalid semantic version"):
            prepare_changelog("1.0.0-alpha", str(f))

    @pytest.mark.parametrize(
        "version",
        ["abc", "1.0", "1", "", "1.0.0.0"],
    )
    def test_rejects_various_invalid_versions(self, tmp_path, basic_changelog, version):
        """Parametrised check for several invalid version strings."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(basic_changelog)
        with pytest.raises(ValueError, match="Invalid semantic version"):
            prepare_changelog(version, str(f))

    @pytest.mark.parametrize("version", ["0.0.1", "1.0.0", "99.99.99"])
    def test_accepts_valid_semver(self, tmp_path, basic_changelog, version):
        """Should succeed with well-formed semver strings."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(basic_changelog)
        prepare_changelog(version, str(f))
        assert f"## [{version}] - TBD" in f.read_text()

    # ── Error handling ────────────────────────────────────────────────────

    def test_raises_for_missing_file(self, tmp_path):
        """Should raise FileNotFoundError if changelog does not exist."""
        with pytest.raises(FileNotFoundError, match="CHANGELOG not found"):
            prepare_changelog("1.0.0", str(tmp_path / "nope.md"))

    def test_raises_for_missing_unreleased(self, tmp_path):
        """Should raise ValueError if there is no Unreleased heading."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(NO_UNRELEASED_CHANGELOG)
        with pytest.raises(ValueError, match="No.*Unreleased"):
            prepare_changelog("1.0.0", str(f))

    # ── Idempotency / double-prepare ──────────────────────────────────────

    def test_double_prepare_creates_two_versions(self, tmp_path, basic_changelog):
        """Running prepare twice with different versions should create two blocks."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(basic_changelog)
        prepare_changelog("1.0.0", str(f))
        # Add a new bullet into Unreleased so second prepare has content
        text = f.read_text()
        text = text.replace(
            "### Added\n\n### Changed",
            "### Added\n\n- Post-1.0 feature\n\n### Changed",
        )
        f.write_text(text)
        prepare_changelog("2.0.0", str(f))
        content = f.read_text()
        assert "## [2.0.0] - TBD" in content
        assert "## [1.0.0] - TBD" in content

    def test_double_prepare_same_version_dedupes_heading(
        self, tmp_path, basic_changelog
    ):
        """Re-preparing the same version must not stack a second heading (#612).

        A reused release branch re-runs prepare for the same base version; the
        result must keep exactly one ## [X.Y.Z] - TBD section that folds in both
        the original and the new Unreleased content.
        """
        f = tmp_path / "CHANGELOG.md"
        f.write_text(basic_changelog)
        prepare_changelog("1.0.0", str(f))
        # Seed new content into the fresh Unreleased for the second pass.
        text = f.read_text()
        text = text.replace(
            "### Added\n\n### Changed",
            "### Added\n\n- Second-pass feature\n\n### Changed",
        )
        f.write_text(text)
        prepare_changelog("1.0.0", str(f))
        content = f.read_text()
        assert content.count("## [1.0.0]") == 1
        assert "## [1.0.0] - TBD" in content
        # Both the original frozen content and the second-pass content survive.
        assert "- New feature X" in content
        assert "- Second-pass feature" in content
        # Unreleased is still present exactly once and precedes the version.
        assert content.count("## Unreleased") == 1
        assert content.index("## Unreleased") < content.index("## [1.0.0]")

    def test_prepare_dedupes_dated_same_version_heading(self, tmp_path):
        """Prepare folds a dated same-version heading into a single TBD section."""
        changelog = """\
# Changelog

## Unreleased

### Added

- Late addition

### Changed

### Deprecated

### Removed

### Fixed

### Security

## [1.0.0](https://github.com/vig-os/devcontainer/releases/tag/1.0.0) - 2026-02-11

### Added

- Already shipped

## [0.2.0] - 2026-01-01

### Added

- Old feature
"""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(changelog)
        prepare_changelog("1.0.0", str(f))
        content = f.read_text()
        assert content.count("## [1.0.0]") == 1
        assert "## [1.0.0] - TBD" in content
        assert "- Late addition" in content
        assert "- Already shipped" in content
        assert "## [0.2.0] - 2026-01-01" in content


# ═════════════════════════════════════════════════════════════════════════════
# reset_unreleased
# ═════════════════════════════════════════════════════════════════════════════


class TestResetUnreleased:
    """Unit tests for reset_unreleased()."""

    def test_creates_fresh_unreleased(self, tmp_path):
        """Should insert Unreleased with all 6 sections."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(RELEASED_ONLY_CHANGELOG)
        reset_unreleased(str(f))
        content = f.read_text()
        assert "## Unreleased" in content
        unreleased_block = content[: content.find("## [1.0.0]")]
        for section in STANDARD_SECTIONS:
            assert f"### {section}" in unreleased_block

    def test_unreleased_before_first_version(self, tmp_path):
        """Unreleased section should precede the first version heading."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(RELEASED_ONLY_CHANGELOG)
        reset_unreleased(str(f))
        content = f.read_text()
        assert content.index("## Unreleased") < content.index("## [1.0.0]")

    def test_preserves_existing_versions(self, tmp_path):
        """All previously-released sections should remain intact."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(RELEASED_ONLY_CHANGELOG)
        reset_unreleased(str(f))
        content = f.read_text()
        assert "## [1.0.0] - 2026-02-06" in content
        assert "## [0.2.0] - 2026-01-01" in content
        assert "- Released feature" in content
        assert "- Old feature" in content

    def test_fails_if_unreleased_already_exists(self, tmp_path):
        """Should raise ValueError when Unreleased heading is already present."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(BASIC_CHANGELOG)
        with pytest.raises(ValueError, match="already exists"):
            reset_unreleased(str(f))

    def test_raises_for_missing_file(self, tmp_path):
        """Should raise FileNotFoundError for a nonexistent changelog."""
        with pytest.raises(FileNotFoundError, match="CHANGELOG not found"):
            reset_unreleased(str(tmp_path / "nope.md"))

    def test_raises_when_no_version_heading(self, tmp_path):
        """Should raise ValueError if there is no version heading to anchor on."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text("# Changelog\n\nSome text but no version headings.\n")
        with pytest.raises(ValueError, match="Could not find"):
            reset_unreleased(str(f))


# ═════════════════════════════════════════════════════════════════════════════
# reset_version_to_tbd
# ═════════════════════════════════════════════════════════════════════════════


class TestResetVersionToTbd:
    """Unit tests for reset_version_to_tbd() (#612 dispatch-start normalizer)."""

    def test_resets_dated_linked_heading(self, tmp_path):
        """A finalized ## [X.Y.Z](…) - DATE heading reverts to ## [X.Y.Z] - TBD."""
        changelog = (
            "# Changelog\n\n## Unreleased\n\n### Added\n\n"
            "## [0.3.7](https://github.com/vig-os/devcontainer/releases/tag/0.3.7)"
            " - 2026-06-22\n\n### Changed\n\n- Smoke-test deploy\n"
        )
        f = tmp_path / "CHANGELOG.md"
        f.write_text(changelog)
        modified = reset_version_to_tbd("0.3.7", str(f))
        content = f.read_text()
        assert modified is True
        assert "## [0.3.7] - TBD" in content
        assert "releases/tag/0.3.7" not in content
        assert "- Smoke-test deploy" in content

    def test_resets_plain_dated_heading(self, tmp_path):
        """A plain ## [X.Y.Z] - DATE heading reverts to TBD."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text("# Changelog\n\n## [0.3.7] - 2026-06-22\n\n### Added\n\n- X\n")
        modified = reset_version_to_tbd("0.3.7", str(f))
        assert modified is True
        assert "## [0.3.7] - TBD" in f.read_text()

    def test_noop_when_already_tbd(self, tmp_path):
        """Already-TBD heading is left unchanged and reports no modification."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(CHANGELOG_WITH_TBD)
        before = f.read_text()
        modified = reset_version_to_tbd("1.0.0", str(f))
        assert modified is False
        assert f.read_text() == before

    def test_noop_when_version_absent(self, tmp_path):
        """Absent version is a no-op (never errors) and leaves the file unchanged."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(CHANGELOG_WITH_TBD)
        before = f.read_text()
        modified = reset_version_to_tbd("9.9.9", str(f))
        assert modified is False
        assert f.read_text() == before

    def test_only_targets_requested_version(self, tmp_path):
        """Other dated versions stay untouched."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(
            "# Changelog\n\n## [0.3.7] - 2026-06-22\n\n## [0.2.0] - 2026-01-01\n"
        )
        reset_version_to_tbd("0.3.7", str(f))
        content = f.read_text()
        assert "## [0.3.7] - TBD" in content
        assert "## [0.2.0] - 2026-01-01" in content

    def test_invalid_version_raises(self, tmp_path):
        """Invalid semver still raises (consistent with sibling commands)."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(CHANGELOG_WITH_TBD)
        with pytest.raises(ValueError, match="Invalid semantic version"):
            reset_version_to_tbd("v1.0.0", str(f))

    def test_raises_for_missing_file(self, tmp_path):
        """Should raise FileNotFoundError for a nonexistent changelog."""
        with pytest.raises(FileNotFoundError, match="CHANGELOG not found"):
            reset_version_to_tbd("1.0.0", str(tmp_path / "nope.md"))


# ═════════════════════════════════════════════════════════════════════════════
# unprepare_changelog
# ═════════════════════════════════════════════════════════════════════════════

TOP_VERSION_TBD_THEN_OLDER = """\
# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] - TBD

### Added

- **Feature** ([#1](https://example.com/1))

## [0.9.0] - 2026-01-01

### Added

- Prior
"""


class TestUnprepareChangelog:
    """Unit tests for unprepare_changelog()."""

    def test_renames_tbd_header(self, tmp_path):
        """Top ## [semver] - TBD becomes ## Unreleased; body preserved."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(TOP_VERSION_TBD_THEN_OLDER)
        assert unprepare_changelog(str(f)) is True
        text = f.read_text()
        assert text.startswith("# Changelog")
        first_h2 = re.search(r"^## .+$", text, re.MULTILINE)
        assert first_h2 is not None
        assert first_h2.group(0) == "## Unreleased"
        assert "## [1.0.0] - TBD" not in text
        assert "**Feature**" in text
        assert "## [0.9.0] - 2026-01-01" in text

    def test_renames_dated_header(self, tmp_path):
        """Top ## [semver] - YYYY-MM-DD becomes ## Unreleased."""
        body = """\
# Changelog

## [2.0.0] - 2026-03-23

### Fixed

- Bug

"""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(body)
        assert unprepare_changelog(str(f)) is True
        assert f.read_text().split("\n")[2] == "## Unreleased"
        assert "- Bug" in f.read_text()

    def test_renames_linked_dated_header(self, tmp_path):
        """Top ## [semver](url) - YYYY-MM-DD becomes ## Unreleased."""
        body = """\
# Changelog

## [2.0.0](https://github.com/o/r/releases/tag/2.0.0) - 2026-03-23

### Fixed

- Bug

"""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(body)
        assert unprepare_changelog(str(f)) is True
        assert f.read_text().split("\n")[2] == "## Unreleased"
        assert "- Bug" in f.read_text()

    def test_noop_when_already_unreleased(self, tmp_path):
        """Returns False and leaves file unchanged."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(BASIC_CHANGELOG)
        before = f.read_text()
        assert unprepare_changelog(str(f)) is False
        assert f.read_text() == before

    def test_raises_no_heading(self, tmp_path):
        """No ## line raises ValueError."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text("# Title only\n\nNo section.\n")
        with pytest.raises(ValueError, match="No top-level"):
            unprepare_changelog(str(f))

    def test_raises_unexpected_heading(self, tmp_path):
        """Non-version first ## heading raises."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text("# C\n\n## Random\n\n- x\n")
        with pytest.raises(ValueError, match="Unexpected first"):
            unprepare_changelog(str(f))

    def test_raises_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="CHANGELOG not found"):
            unprepare_changelog(str(tmp_path / "missing.md"))


class TestCmdUnprepare:
    """Tests for cmd_unprepare handler."""

    def _make_args(self, filepath):
        from argparse import Namespace

        return Namespace(file=filepath)

    def test_output_when_modified(self, tmp_path, capsys):
        f = tmp_path / "CHANGELOG.md"
        f.write_text(TOP_VERSION_TBD_THEN_OLDER)
        cmd_unprepare(self._make_args(str(f)))
        out = capsys.readouterr().out
        assert "Renamed" in out
        assert "## Unreleased" in f.read_text()

    def test_output_when_noop(self, tmp_path, capsys):
        f = tmp_path / "CHANGELOG.md"
        f.write_text(BASIC_CHANGELOG)
        cmd_unprepare(self._make_args(str(f)))
        out = capsys.readouterr().out
        assert "no changes" in out.lower() or "already" in out.lower()


# ═════════════════════════════════════════════════════════════════════════════
# finalize_release_date
# ═════════════════════════════════════════════════════════════════════════════


class TestFinalizeReleaseDate:
    """Unit tests for finalize_release_date()."""

    # ── Happy path ────────────────────────────────────────────────────────

    def test_replaces_tbd_with_date(self, tmp_path):
        """Should substitute TBD → actual date and add release tag link."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(CHANGELOG_WITH_TBD)
        finalize_release_date(
            "1.0.0", "2026-02-11", str(f), github_repository=_FINALIZE_TEST_REPO
        )
        content = f.read_text()
        assert (
            f"## [1.0.0](https://github.com/{_FINALIZE_TEST_REPO}/releases/tag/1.0.0) - 2026-02-11"
            in content
        )
        assert "## [1.0.0] - TBD" not in content

    def test_preserves_version_content(self, tmp_path):
        """All bullets in the version section should remain."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(CHANGELOG_WITH_TBD)
        finalize_release_date(
            "1.0.0", "2026-02-11", str(f), github_repository=_FINALIZE_TEST_REPO
        )
        content = f.read_text()
        heading = f"## [1.0.0](https://github.com/{_FINALIZE_TEST_REPO}/releases/tag/1.0.0) - 2026-02-11"
        version_start = content.find(heading)
        version_end = content.find("## [0.2.0]")
        version_section = content[version_start:version_end]
        assert "- Feature X" in version_section
        assert "- Feature Y" in version_section
        assert "- Bug A" in version_section

    def test_preserves_other_sections(self, tmp_path):
        """Other versions and Unreleased should stay untouched."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(CHANGELOG_WITH_TBD)
        finalize_release_date(
            "1.0.0", "2026-02-11", str(f), github_repository=_FINALIZE_TEST_REPO
        )
        content = f.read_text()
        assert "## [0.2.0] - 2026-01-01" in content
        assert "## Unreleased" in content

    def test_handles_multiple_tbd_versions(self, tmp_path):
        """Only the specified version's TBD should be replaced."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(MULTIPLE_TBD_CHANGELOG)
        finalize_release_date(
            "1.0.0", "2026-02-11", str(f), github_repository=_FINALIZE_TEST_REPO
        )
        content = f.read_text()
        assert (
            f"## [1.0.0](https://github.com/{_FINALIZE_TEST_REPO}/releases/tag/1.0.0) - 2026-02-11"
            in content
        )
        assert "## [2.0.0] - TBD" in content

    def test_special_characters_in_content(self, tmp_path):
        """Brackets, parentheses, dollar signs etc. should not confuse regex."""
        changelog = """\
# Changelog

## [1.0.0] - TBD

### Added

- Feature with [brackets] and (parentheses)
- Feature with special $chars* and .dots
"""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(changelog)
        finalize_release_date(
            "1.0.0", "2026-02-11", str(f), github_repository=_FINALIZE_TEST_REPO
        )
        content = f.read_text()
        assert (
            f"## [1.0.0](https://github.com/{_FINALIZE_TEST_REPO}/releases/tag/1.0.0) - 2026-02-11"
            in content
        )
        assert "[brackets]" in content
        assert "$chars*" in content

    def test_uses_github_repository_from_env(self, tmp_path, monkeypatch):
        """GITHUB_REPOSITORY should supply the owner/repo slug when unset on the call."""
        monkeypatch.setenv("GITHUB_REPOSITORY", "acme/cool-widget")
        f = tmp_path / "CHANGELOG.md"
        f.write_text(CHANGELOG_WITH_TBD)
        finalize_release_date("1.0.0", "2026-02-11", str(f))
        assert "https://github.com/acme/cool-widget/releases/tag/1.0.0" in f.read_text()

    def test_github_repository_param_overrides_env(self, tmp_path, monkeypatch):
        """Explicit github_repository wins over GITHUB_REPOSITORY."""
        monkeypatch.setenv("GITHUB_REPOSITORY", "wrong/repo")
        f = tmp_path / "CHANGELOG.md"
        f.write_text(CHANGELOG_WITH_TBD)
        finalize_release_date(
            "1.0.0",
            "2026-02-11",
            str(f),
            github_repository="right/correct-repo",
        )
        assert (
            "https://github.com/right/correct-repo/releases/tag/1.0.0" in f.read_text()
        )
        assert "wrong/repo" not in f.read_text()

    # ── Version validation ────────────────────────────────────────────────

    def test_rejects_invalid_semver(self, tmp_path):
        """Should raise for malformed version strings."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(CHANGELOG_WITH_TBD)
        with pytest.raises(ValueError, match="Invalid semantic version"):
            finalize_release_date(
                "1.0",
                "2026-02-11",
                str(f),
                github_repository=_FINALIZE_TEST_REPO,
            )

    def test_rejects_v_prefix(self, tmp_path):
        """Should raise for 'v' prefixed versions."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(CHANGELOG_WITH_TBD)
        with pytest.raises(ValueError, match="Invalid semantic version"):
            finalize_release_date(
                "v1.0.0",
                "2026-02-11",
                str(f),
                github_repository=_FINALIZE_TEST_REPO,
            )

    # ── Date validation ───────────────────────────────────────────────────

    @pytest.mark.parametrize(
        "bad_date",
        [
            "2026/02/11",
            "02-11-2026",
            "2026-2-11",
            "2026-02-1",
            "11-02-2026",
            "not-a-date",
            "",
        ],
    )
    def test_rejects_invalid_date_formats(self, tmp_path, bad_date):
        """Should raise ValueError for dates not matching YYYY-MM-DD."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(CHANGELOG_WITH_TBD)
        with pytest.raises(ValueError, match="Invalid date"):
            finalize_release_date(
                "1.0.0", bad_date, str(f), github_repository=_FINALIZE_TEST_REPO
            )

    # ── Error handling ────────────────────────────────────────────────────

    def test_raises_without_github_repository(self, tmp_path, monkeypatch):
        """Should raise when neither argument nor GITHUB_REPOSITORY is set."""
        monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
        f = tmp_path / "CHANGELOG.md"
        f.write_text(CHANGELOG_WITH_TBD)
        with pytest.raises(ValueError, match="GitHub repository is required"):
            finalize_release_date("1.0.0", "2026-02-11", str(f))

    @pytest.mark.parametrize(
        "bad_slug",
        [
            "too-many/slash/parts",
            "has spaces/repo",
            "owner/re(po)",
        ],
    )
    def test_rejects_invalid_github_repository_slug(self, tmp_path, bad_slug):
        """Should raise for invalid owner/repo slug (segment count or characters)."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(CHANGELOG_WITH_TBD)
        with pytest.raises(ValueError, match="Invalid github_repository"):
            finalize_release_date(
                "1.0.0",
                "2026-02-11",
                str(f),
                github_repository=bad_slug,
            )

    def test_fails_version_not_found(self, tmp_path):
        """Should raise when the specified version doesn't exist."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(CHANGELOG_WITH_TBD)
        with pytest.raises(ValueError, match="not found"):
            finalize_release_date(
                "9.9.9", "2026-02-11", str(f), github_repository=_FINALIZE_TEST_REPO
            )

    def test_fails_already_finalized(self, tmp_path):
        """Should raise when version already has a real date (not TBD)."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(CHANGELOG_WITH_TBD)
        with pytest.raises(ValueError, match="not found"):
            finalize_release_date(
                "0.2.0", "2026-02-11", str(f), github_repository=_FINALIZE_TEST_REPO
            )

    def test_raises_for_missing_file(self, tmp_path):
        """Should raise FileNotFoundError for nonexistent file."""
        with pytest.raises(FileNotFoundError, match="CHANGELOG not found"):
            finalize_release_date(
                "1.0.0",
                "2026-02-11",
                str(tmp_path / "nope.md"),
                github_repository=_FINALIZE_TEST_REPO,
            )

    def test_idempotent_when_already_finalized(self, tmp_path):
        """Re-running finalize on a version this tool already finalized is a no-op.

        Guards #612: a reused release branch can re-run finalize against an
        already-dated heading; the second run must succeed without changing it.
        """
        f = tmp_path / "CHANGELOG.md"
        f.write_text(CHANGELOG_WITH_TBD)
        finalize_release_date(
            "1.0.0", "2026-02-11", str(f), github_repository=_FINALIZE_TEST_REPO
        )
        after_first = f.read_text()
        # Second finalize on the same version must not raise...
        finalize_release_date(
            "1.0.0", "2026-02-11", str(f), github_repository=_FINALIZE_TEST_REPO
        )
        # ...and must leave the already-finalized heading untouched.
        assert f.read_text() == after_first

    def test_idempotent_keeps_original_date_when_already_finalized(self, tmp_path):
        """A later finalize with a different date is a no-op once already finalized."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(CHANGELOG_WITH_TBD)
        finalize_release_date(
            "1.0.0", "2026-02-11", str(f), github_repository=_FINALIZE_TEST_REPO
        )
        after_first = f.read_text()
        finalize_release_date(
            "1.0.0", "2026-03-01", str(f), github_repository=_FINALIZE_TEST_REPO
        )
        assert f.read_text() == after_first


# ═════════════════════════════════════════════════════════════════════════════
# Full prepare → finalize cycle
# ═════════════════════════════════════════════════════════════════════════════


class TestPrepareThenFinalize:
    """Integration: prepare followed by finalize should produce a clean release."""

    def test_full_cycle(self, tmp_path, basic_changelog):
        """prepare → finalize produces a dated version and clean Unreleased."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(basic_changelog)

        prepare_changelog("1.0.0", str(f))
        finalize_release_date(
            "1.0.0", "2026-02-11", str(f), github_repository=_FINALIZE_TEST_REPO
        )

        content = f.read_text()
        assert (
            f"## [1.0.0](https://github.com/{_FINALIZE_TEST_REPO}/releases/tag/1.0.0) - 2026-02-11"
            in content
        )
        assert "TBD" not in content
        assert "## Unreleased" in content
        assert content.index("## Unreleased") < content.index("## [1.0.0]")

    def test_prepare_finalize_reset_cycle(self, tmp_path):
        """prepare → finalize → (simulate merge) → reset restores Unreleased."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(MINIMAL_CHANGELOG)

        prepare_changelog("1.0.0", str(f))
        finalize_release_date(
            "1.0.0", "2026-02-11", str(f), github_repository=_FINALIZE_TEST_REPO
        )

        # Simulate merging to main: remove the Unreleased block
        content = f.read_text()
        # Remove everything from "## Unreleased" to just before "## [1.0.0]"
        unreleased_start = content.index("## Unreleased")
        version_start = content.index("## [1.0.0]")
        content = content[:unreleased_start] + content[version_start:]
        f.write_text(content)

        # Now reset
        reset_unreleased(str(f))
        content = f.read_text()
        assert "## Unreleased" in content
        assert content.index("## Unreleased") < content.index("## [1.0.0]")


# ═════════════════════════════════════════════════════════════════════════════
# CLI command handlers (cmd_*)
# ═════════════════════════════════════════════════════════════════════════════


class TestCmdPrepare:
    """Tests for cmd_prepare handler (stdout output)."""

    def _make_args(self, version, filepath):
        """Create a minimal args namespace."""
        from argparse import Namespace

        return Namespace(version=version, file=filepath)

    def test_output_success_with_sections(self, tmp_path, basic_changelog, capsys):
        """Should print success and list moved sections."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(basic_changelog)
        cmd_prepare(self._make_args("1.0.0", str(f)))
        out = capsys.readouterr().out
        assert "1.0.0" in out
        assert "✓" in out
        assert "Added" in out
        assert "Changed" in out
        assert "Fixed" in out

    def test_output_warning_empty_unreleased(self, tmp_path, capsys):
        """Should print warning when Unreleased is empty."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(EMPTY_UNRELEASED_CHANGELOG)
        cmd_prepare(self._make_args("1.0.0", str(f)))
        out = capsys.readouterr().out
        assert "Warning" in out or "No content" in out

    def test_output_mentions_fresh_unreleased(self, tmp_path, basic_changelog, capsys):
        """Should mention that a fresh Unreleased section was created."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(basic_changelog)
        cmd_prepare(self._make_args("1.0.0", str(f)))
        out = capsys.readouterr().out
        assert "Unreleased" in out


class TestCmdValidate:
    """Tests for cmd_validate handler."""

    def _make_args(self, filepath):
        from argparse import Namespace

        return Namespace(file=filepath)

    def test_success_output(self, tmp_path, basic_changelog, capsys):
        """Should print success when valid."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(basic_changelog)
        cmd_validate(self._make_args(str(f)))
        out = capsys.readouterr().out
        assert "✓" in out

    def test_exits_on_missing_unreleased(self, tmp_path):
        """Should sys.exit(1) when Unreleased missing."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(NO_UNRELEASED_CHANGELOG)
        with pytest.raises(SystemExit, match="1"):
            cmd_validate(self._make_args(str(f)))

    def test_exits_on_empty_unreleased(self, tmp_path):
        """Should sys.exit(1) when Unreleased is empty."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(EMPTY_UNRELEASED_CHANGELOG)
        with pytest.raises(SystemExit, match="1"):
            cmd_validate(self._make_args(str(f)))


class TestCmdReset:
    """Tests for cmd_reset handler."""

    def _make_args(self, filepath):
        from argparse import Namespace

        return Namespace(file=filepath)

    def test_success_output(self, tmp_path, capsys):
        """Should print success message."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(RELEASED_ONLY_CHANGELOG)
        cmd_reset(self._make_args(str(f)))
        out = capsys.readouterr().out
        assert "✓" in out
        assert "Reset" in out


class TestCmdResetVersion:
    """Tests for cmd_reset_version handler."""

    def _make_args(self, version, filepath):
        from argparse import Namespace

        return Namespace(version=version, file=filepath)

    def test_reset_output(self, tmp_path, capsys):
        """Should report the version was reset to TBD."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text("# Changelog\n\n## [0.3.7] - 2026-06-22\n")
        cmd_reset_version(self._make_args("0.3.7", str(f)))
        out = capsys.readouterr().out
        assert "✓" in out
        assert "0.3.7" in out

    def test_noop_output(self, tmp_path, capsys):
        """Should still succeed (no error) when there is nothing to reset."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(CHANGELOG_WITH_TBD)
        cmd_reset_version(self._make_args("9.9.9", str(f)))
        out = capsys.readouterr().out
        assert "9.9.9" in out


class TestCmdFinalize:
    """Tests for cmd_finalize handler."""

    def _make_args(
        self, version, date, filepath, github_repository=_FINALIZE_TEST_REPO
    ):
        from argparse import Namespace

        return Namespace(
            version=version,
            date=date,
            file=filepath,
            github_repository=github_repository,
        )

    def test_success_output(self, tmp_path, capsys):
        """Should print version and date."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(CHANGELOG_WITH_TBD)
        cmd_finalize(self._make_args("1.0.0", "2026-02-11", str(f)))
        out = capsys.readouterr().out
        assert "1.0.0" in out
        assert "2026-02-11" in out


# ═════════════════════════════════════════════════════════════════════════════
# main() CLI parser
# ═════════════════════════════════════════════════════════════════════════════


class TestMainCLI:
    """Tests for the argparse-based main() entry point."""

    def test_no_command_exits(self):
        """Calling main with no arguments should exit non-zero."""
        with patch("sys.argv", ["prepare-changelog.py"]), pytest.raises(SystemExit):
            main()

    def test_unknown_command_exits(self):
        """An unknown sub-command should exit non-zero."""
        with (
            patch("sys.argv", ["prepare-changelog.py", "bogus"]),
            pytest.raises(SystemExit),
        ):
            main()

    def test_prepare_via_main(self, tmp_path, basic_changelog):
        """main() with 'prepare' should create a version section."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(basic_changelog)
        with patch("sys.argv", ["prog", "prepare", "1.0.0", str(f)]):
            main()
        assert "## [1.0.0] - TBD" in f.read_text()

    def test_validate_via_main(self, tmp_path, basic_changelog, capsys):
        """main() with 'validate' should succeed when valid."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(basic_changelog)
        with patch("sys.argv", ["prog", "validate", str(f)]):
            main()
        out = capsys.readouterr().out
        assert "✓" in out

    def test_reset_via_main(self, tmp_path):
        """main() with 'reset' should create an Unreleased section."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(RELEASED_ONLY_CHANGELOG)
        with patch("sys.argv", ["prog", "reset", str(f)]):
            main()
        assert "## Unreleased" in f.read_text()

    def test_finalize_via_main(self, tmp_path):
        """main() with 'finalize' should replace TBD with date and release link."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(CHANGELOG_WITH_TBD)
        with patch(
            "sys.argv",
            [
                "prog",
                "finalize",
                "1.0.0",
                "2026-02-11",
                str(f),
                "--github-repository",
                _FINALIZE_TEST_REPO,
            ],
        ):
            main()
        assert (
            f"## [1.0.0](https://github.com/{_FINALIZE_TEST_REPO}/releases/tag/1.0.0) - 2026-02-11"
            in f.read_text()
        )

    def test_reset_version_via_main(self, tmp_path):
        """main() with 'reset-version' should revert a dated heading to TBD."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text("# Changelog\n\n## [0.3.7] - 2026-06-22\n")
        with patch("sys.argv", ["prog", "reset-version", "0.3.7", str(f)]):
            main()
        assert "## [0.3.7] - TBD" in f.read_text()

    def test_unprepare_via_main(self, tmp_path):
        """main() with 'unprepare' should rename top version heading."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(TOP_VERSION_TBD_THEN_OLDER)
        with patch("sys.argv", ["prog", "unprepare", str(f)]):
            main()
        first = re.search(r"^## .+$", f.read_text(), re.MULTILINE)
        assert first is not None
        assert first.group(0) == "## Unreleased"

    def test_main_catches_exceptions(self, tmp_path):
        """main() should convert exceptions to stderr + exit(1)."""
        with (
            patch("sys.argv", ["prog", "prepare", "bad!", str(tmp_path / "nope.md")]),
            pytest.raises(SystemExit),
        ):
            main()


# ═════════════════════════════════════════════════════════════════════════════
# CLI subprocess integration tests (smoke tests)
# ═════════════════════════════════════════════════════════════════════════════


class TestCLISubprocess:
    """
    Subprocess-based smoke tests verifying the script works end-to-end as a
    standalone process.  These complement the import-based unit tests above.
    """

    def _run(self, *args, env=None):
        """Helper to invoke the CLI entry point."""
        if ENTRY_POINT is None:
            pytest.skip("prepare-changelog entry point not installed")
        return subprocess.run(
            [ENTRY_POINT, *args],
            capture_output=True,
            text=True,
            env=env,
        )

    # ── prepare ───────────────────────────────────────────────────────────

    def test_prepare_e2e(self, tmp_path):
        """Full prepare cycle via subprocess."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(BASIC_CHANGELOG)
        result = self._run("prepare", "1.0.0", str(f))
        assert result.returncode == 0
        content = f.read_text()
        assert "## [1.0.0] - TBD" in content
        assert "## Unreleased" in content

    def test_prepare_invalid_version_e2e(self, tmp_path):
        """Invalid version via subprocess should exit non-zero."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(BASIC_CHANGELOG)
        result = self._run("prepare", "v1.0.0", str(f))
        assert result.returncode != 0
        assert "Invalid" in result.stderr or "version" in result.stderr.lower()

    def test_prepare_missing_file_e2e(self, tmp_path):
        """Missing file via subprocess should exit non-zero."""
        result = self._run("prepare", "1.0.0", str(tmp_path / "nope.md"))
        assert result.returncode != 0

    # ── validate ──────────────────────────────────────────────────────────

    def test_validate_passes_e2e(self, tmp_path):
        """Validate should succeed when Unreleased has content."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(BASIC_CHANGELOG)
        result = self._run("validate", str(f))
        assert result.returncode == 0
        assert "✓" in result.stdout

    def test_validate_fails_empty_e2e(self, tmp_path):
        """Validate should fail when Unreleased is empty."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(EMPTY_UNRELEASED_CHANGELOG)
        result = self._run("validate", str(f))
        assert result.returncode == 1
        assert "empty" in result.stderr.lower()

    # ── reset ─────────────────────────────────────────────────────────────

    def test_reset_e2e(self, tmp_path):
        """Reset should create Unreleased section."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(RELEASED_ONLY_CHANGELOG)
        result = self._run("reset", str(f))
        assert result.returncode == 0
        assert "## Unreleased" in f.read_text()

    def test_reset_fails_if_unreleased_exists_e2e(self, tmp_path):
        """Reset should fail when Unreleased already present."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(BASIC_CHANGELOG)
        result = self._run("reset", str(f))
        assert result.returncode != 0

    # ── finalize ──────────────────────────────────────────────────────────

    def test_finalize_e2e(self, tmp_path):
        """Finalize should replace TBD with date and release tag URL."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(CHANGELOG_WITH_TBD)
        result = self._run(
            "finalize",
            "1.0.0",
            "2026-02-11",
            str(f),
            "--github-repository",
            _FINALIZE_TEST_REPO,
        )
        assert result.returncode == 0
        assert (
            f"## [1.0.0](https://github.com/{_FINALIZE_TEST_REPO}/releases/tag/1.0.0) - 2026-02-11"
            in f.read_text()
        )

    def test_finalize_e2e_requires_repo_without_env(self, tmp_path):
        """Finalize fails when GITHUB_REPOSITORY is unset and flag omitted."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(CHANGELOG_WITH_TBD)
        env = {k: v for k, v in os.environ.items() if k != "GITHUB_REPOSITORY"}
        result = self._run("finalize", "1.0.0", "2026-02-11", str(f), env=env)
        assert result.returncode != 0
        assert "GitHub repository" in result.stderr

    def test_finalize_invalid_date_e2e(self, tmp_path):
        """Invalid date via subprocess should exit non-zero."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(CHANGELOG_WITH_TBD)
        result = self._run(
            "finalize",
            "1.0.0",
            "02/11/2026",
            str(f),
            "--github-repository",
            _FINALIZE_TEST_REPO,
        )
        assert result.returncode != 0
        assert "Invalid" in result.stderr or "date" in result.stderr.lower()

    def test_finalize_version_not_found_e2e(self, tmp_path):
        """Non-existent version via subprocess should exit non-zero."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(CHANGELOG_WITH_TBD)
        result = self._run(
            "finalize",
            "9.9.9",
            "2026-02-11",
            str(f),
            "--github-repository",
            _FINALIZE_TEST_REPO,
        )
        assert result.returncode != 0

    # ── reset-version ─────────────────────────────────────────────────────

    def test_reset_version_e2e(self, tmp_path):
        """reset-version via subprocess reverts a dated heading to TBD."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(
            "# Changelog\n\n## [0.3.7]"
            "(https://github.com/vig-os/devcontainer/releases/tag/0.3.7)"
            " - 2026-06-22\n"
        )
        result = self._run("reset-version", "0.3.7", str(f))
        assert result.returncode == 0
        assert "## [0.3.7] - TBD" in f.read_text()

    def test_reset_version_noop_e2e(self, tmp_path):
        """reset-version is a clean no-op when the version is absent."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(CHANGELOG_WITH_TBD)
        before = f.read_text()
        result = self._run("reset-version", "9.9.9", str(f))
        assert result.returncode == 0
        assert f.read_text() == before

    # ── unprepare ─────────────────────────────────────────────────────────

    def test_unprepare_e2e(self, tmp_path):
        """unprepare via subprocess renames top version heading."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(TOP_VERSION_TBD_THEN_OLDER)
        result = self._run("unprepare", str(f))
        assert result.returncode == 0
        first = re.search(r"^## .+$", f.read_text(), re.MULTILINE)
        assert first is not None
        assert first.group(0) == "## Unreleased"

    def test_unprepare_noop_e2e(self, tmp_path):
        """unprepare leaves Unreleased changelog unchanged."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(BASIC_CHANGELOG)
        before = f.read_text()
        result = self._run("unprepare", str(f))
        assert result.returncode == 0
        assert f.read_text() == before
