"""Tests for Renovate PR changelog insertion (Refs: #506)."""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

import pytest
from vig_utils.renovate_changelog_pr import (
    format_adoption_entry,
    format_changelog_entry,
    insert_renovate_changelog_entry,
    main,
    parse_adoption_title,
    parse_renovate_pr_updates,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_parse_title_single_dependency_digest() -> None:
    title = (
        "ci(actions): update actions/checkout digest to "
        "de0fac2e4500dabe0009e67214ff5f5447ce83dd"
    )
    updates = parse_renovate_pr_updates(title, "")
    assert len(updates) == 1
    pkg, old_v, new_v = updates[0]
    assert pkg == "actions/checkout"
    assert old_v is None
    assert new_v == "de0fac2e4500dabe0009e67214ff5f5447ce83dd"


def test_parse_title_single_dependency_version() -> None:
    title = "build(pip): update dependency urllib3 to v2.6.3"
    updates = parse_renovate_pr_updates(title, "")
    assert updates == [("urllib3", None, "v2.6.3")]


def test_parse_body_markdown_table() -> None:
    body = textwrap.dedent(
        """
        This PR contains the following updates:

        | Package | Type | Update | Change |
        |---------|------|--------|--------|
        | [actions/checkout](https://github.com/actions/checkout) | action | minor | `v4.1.0` -> `v4.2.0` |
        | [actions/cache](https://github.com/actions/cache) | action | patch | `v4.0.0` -> `v4.0.1` |
        """
    ).strip()
    updates = parse_renovate_pr_updates("chore(deps): update all", body)
    assert len(updates) == 2
    assert updates[0][0] == "actions/checkout"
    assert updates[0][1] == "v4.1.0"
    assert updates[0][2] == "v4.2.0"
    assert updates[1][0] == "actions/cache"


def test_parse_body_markdown_table_unicode_arrow() -> None:
    # Renovate renders the change cell with a Unicode arrow (U+2192), not ASCII "->".
    body = textwrap.dedent(
        """
        This PR contains the following updates:

        | Package | Type | Update | Change |
        |---------|------|--------|--------|
        | [docker/login-action](https://github.com/docker/login-action) | action | minor | `v4.2.0` → `v4.4.0` |
        | [aquasecurity/trivy](https://github.com/aquasecurity/trivy) | uses-with | minor | `v0.71.2` → `v0.72.0` |
        """
    ).strip()
    updates = parse_renovate_pr_updates("ci(actions): update github-actions", body)
    assert len(updates) == 2
    assert updates[0] == ("docker/login-action", "v4.2.0", "v4.4.0")
    assert updates[1] == ("aquasecurity/trivy", "v0.71.2", "v0.72.0")


def test_parse_change_cell_unicode_arrow_digest() -> None:
    # Unquoted digest cell with a Unicode arrow must also parse.
    body = textwrap.dedent(
        """
        | Package | Type | Update | Change |
        |---------|------|--------|--------|
        | [actions/checkout](https://github.com/actions/checkout) | action | digest | abc1234 → def5678 |
        """
    ).strip()
    updates = parse_renovate_pr_updates("chore(deps): update all", body)
    assert updates == [("actions/checkout", "abc1234", "def5678")]


def test_format_single_with_old_new() -> None:
    entry = format_changelog_entry(
        42,
        "https://github.com/vig-os/devcontainer",
        [("actions/checkout", "v4.1.0", "v4.2.0")],
    )
    assert "Renovate: update `actions/checkout` from `v4.1.0` to `v4.2.0`" in entry
    assert "[#42](https://github.com/vig-os/devcontainer/pull/42)" in entry


def test_format_grouped() -> None:
    entry = format_changelog_entry(
        99,
        "https://github.com/vig-os/devcontainer",
        [
            ("actions/checkout", "v4.1.0", "v4.2.0"),
            ("actions/cache", "v4.0.0", "v4.0.1"),
        ],
    )
    assert "**Renovate dependency update**" in entry
    assert "[#99](https://github.com/vig-os/devcontainer/pull/99)" in entry
    assert "Update `actions/checkout` from `v4.1.0` to `v4.2.0`" in entry
    assert "Update `actions/cache` from `v4.0.0` to `v4.0.1`" in entry


def test_format_single_missing_old() -> None:
    entry = format_changelog_entry(
        1,
        "https://github.com/vig-os/devcontainer",
        [("actions/checkout", None, "de0fac2e4500dabe0009e67214ff5f5447ce83dd")],
    )
    assert (
        "Renovate: update `actions/checkout` to `de0fac2e4500dabe0009e67214ff5f5447ce83dd`"
        in entry
    )


def test_insert_prepends_to_changed_section() -> None:
    """New entries go at the top of ### Changed, above existing bullets."""
    changelog = textwrap.dedent(
        """\
        ## Unreleased

        ### Added

        ### Changed

        - **Existing** ([#1](https://github.com/o/r/pull/1))

        ### Deprecated
        """
    )
    entry = "- **New** ([#2](https://github.com/o/r/pull/2))\n"
    new_content, did = insert_renovate_changelog_entry(changelog, 2, entry)
    assert did is True
    assert new_content.index(entry) < new_content.index("**Existing**")
    assert new_content.index(entry) < new_content.index("### Deprecated")
    assert "**Existing**" in new_content


def test_insert_preserves_blank_line_before_next_heading() -> None:
    """Keep-a-Changelog: blank line between list items and following ### heading."""
    changelog = textwrap.dedent(
        """\
        ## Unreleased

        ### Changed

        - **Existing** ([#1](https://github.com/o/r/pull/1))

        ### Deprecated
        """
    )
    entry = "- **New** ([#2](https://github.com/o/r/pull/2))\n"
    new_content, did = insert_renovate_changelog_entry(changelog, 2, entry)
    assert did is True
    assert "\n\n### Deprecated\n" in new_content


def test_insert_idempotent() -> None:
    changelog = textwrap.dedent(
        """\
        ## Unreleased

        ### Changed

        - **Renovate** ([#5](https://github.com/o/r/pull/5))

        ### Deprecated
        """
    )
    entry = "- **Dup** ([#5](https://github.com/o/r/pull/5))\n"
    new_content, did = insert_renovate_changelog_entry(changelog, 5, entry)
    assert did is False
    assert new_content == changelog


def test_insert_above_subheading_in_changed() -> None:
    """Renovate entries land as a plain ### Changed bullet, above any #### sub-heading."""
    changelog = textwrap.dedent(
        """\
        ## Unreleased

        ### Changed

        #### Modules

        - **Module thing** ([#1](https://github.com/o/r/pull/1))

        ### Deprecated
        """
    )
    entry = "- **Renovate: update `x`** ([#2](https://github.com/o/r/pull/2))\n"
    new_content, did = insert_renovate_changelog_entry(changelog, 2, entry)
    assert did is True
    # Plain bullet at the top of ### Changed, not nested under #### Modules
    assert new_content.index(entry) < new_content.index("#### Modules")
    assert "### Changed\n\n- **Renovate" in new_content
    # Keep-a-Changelog spacing preserved before the sub-heading
    assert "\n\n#### Modules" in new_content


def test_insert_changed_is_last_section_before_version() -> None:
    """### Changed with no following ### subsection still gets new bullets."""
    changelog = textwrap.dedent(
        """\
        ## Unreleased

        ### Changed

        - **Existing** ([#1](https://github.com/o/r/pull/1))

        ## [0.1.0] - 2020-01-01
        """
    )
    entry = "- **New** ([#2](https://github.com/o/r/pull/2))\n"
    new_content, did = insert_renovate_changelog_entry(changelog, 2, entry)
    assert did is True
    assert new_content.index(entry) < new_content.index("## [0.1.0]")
    assert "**Existing**" in new_content


def test_insert_empty_changed_section() -> None:
    changelog = textwrap.dedent(
        """\
        ## Unreleased

        ### Changed

        ### Deprecated
        """
    )
    entry = "- **X** ([#3](https://github.com/o/r/pull/3))\n"
    new_content, did = insert_renovate_changelog_entry(changelog, 3, entry)
    assert did is True
    assert entry.strip() in new_content
    assert "### Changed" in new_content
    # Keep-a-Changelog: blank line between ### Changed heading and first list item
    assert "### Changed\n\n- **X**" in new_content


# ---------------------------------------------------------------------------
# Devkit adoption PRs (Refs: #1404)
# ---------------------------------------------------------------------------


def test_parse_adoption_title_final() -> None:
    assert parse_adoption_title("chore: adopt devkit 1.7.0") == "1.7.0"


def test_parse_adoption_title_rc() -> None:
    assert parse_adoption_title("chore: adopt devkit 1.8.0-rc2") == "1.8.0-rc2"


@pytest.mark.parametrize(
    "title",
    [
        "build(pip): update dependency urllib3 to v2.6.3",
        "chore: adopt devkit",
        "chore: adopt devkit v1.7.0",
        "feat: adopt devkit 1.7.0",
        "chore: adopt devkit 1.7.0 and more",
    ],
)
def test_parse_adoption_title_rejects_non_adoption(title: str) -> None:
    assert parse_adoption_title(title) is None


def test_format_adoption_entry() -> None:
    entry = format_adoption_entry(
        141, "https://github.com/vig-os/commit-action", "1.7.0"
    )
    assert entry.startswith("- **Adopt vigOS devkit 1.7.0**")
    assert "[#141](https://github.com/vig-os/commit-action/pull/141)" in entry
    assert (
        "[release notes](https://github.com/vig-os/devkit/releases/tag/1.7.0)" in entry
    )
    assert entry.endswith("\n")


def test_adoption_entry_inserts_and_dedups() -> None:
    changelog = textwrap.dedent(
        """\
        ## Unreleased

        ### Changed

        - **Existing** ([#1](https://github.com/o/r/pull/1))

        ### Deprecated
        """
    )
    entry = format_adoption_entry(141, "https://github.com/o/r", "1.7.0")
    new_content, did = insert_renovate_changelog_entry(changelog, 141, entry)
    assert did is True
    assert new_content.index("Adopt vigOS devkit 1.7.0") < new_content.index(
        "**Existing**"
    )
    again, did2 = insert_renovate_changelog_entry(new_content, 141, entry)
    assert did2 is False
    assert again == new_content


def test_main_adoption_end_to_end(tmp_path: Path) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        textwrap.dedent(
            """\
            ## Unreleased

            ### Changed

            ### Deprecated
            """
        ),
        encoding="utf-8",
    )
    rc = main(
        [
            "--changelog",
            str(changelog),
            "--pr-number",
            "141",
            "--title",
            "chore: adopt devkit 1.7.0",
            "--repo-url",
            "https://github.com/vig-os/commit-action",
        ]
    )
    assert rc == 0
    text = changelog.read_text(encoding="utf-8")
    assert "### Changed\n\n- **Adopt vigOS devkit 1.7.0**" in text
    assert "[#141](https://github.com/vig-os/commit-action/pull/141)" in text


def test_main_adoption_ignores_body(tmp_path: Path) -> None:
    """An adoption PR body must not be fed through the Renovate table parser."""
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        textwrap.dedent(
            """\
            ## Unreleased

            ### Changed

            ### Deprecated
            """
        ),
        encoding="utf-8",
    )
    body = "| Package | Change |\n|---|---|\n| [x](https://x) | `1` -> `2` |"
    rc = main(
        [
            "--changelog",
            str(changelog),
            "--pr-number",
            "7",
            "--title",
            "chore: adopt devkit 1.8.0-rc1",
            "--body",
            body,
            "--repo-url",
            "https://github.com/o/r",
        ]
    )
    assert rc == 0
    text = changelog.read_text(encoding="utf-8")
    assert "Adopt vigOS devkit 1.8.0-rc1" in text
    assert "Renovate" not in text


def test_main_missing_changelog_is_noop(tmp_path: Path) -> None:
    """Consumers without a CHANGELOG.md (trunk repos) must no-op, not crash."""
    rc = main(
        [
            "--changelog",
            str(tmp_path / "CHANGELOG.md"),
            "--pr-number",
            "141",
            "--title",
            "chore: adopt devkit 1.7.0",
            "--repo-url",
            "https://github.com/o/r",
        ]
    )
    assert rc == 0
    assert not (tmp_path / "CHANGELOG.md").exists()
